from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasBusiness, IsOwnerOrReadOnly

from . import clickpesa, services, sonicpesa
from .models import Plan, Subscription, SubscriptionPayment
from .serializers import PlanSerializer, SubscriptionPaymentSerializer, SubscriptionSerializer


class PaymentGatewayError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'The mobile money service did not accept the payment. Please try again.'
    default_code = 'payment_gateway_error'


class PlanListView(generics.ListAPIView):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class CurrentSubscriptionView(APIView):
    permission_classes = [HasBusiness]

    def get(self, request):
        business = request.user.business
        subscription = getattr(business, 'subscription', None) or Subscription.start_trial(business)
        return Response({
            **SubscriptionSerializer(subscription).data,
            # Whether the app may offer "Control number", and the M-Pesa number to show in its steps
            'control_numbers': {
                'enabled': clickpesa.is_enabled(),
                'mpesa_business_number': settings.CLICKPESA_MPESA_BUSINESS_NUMBER,
            },
        })


class SubscriptionPaymentListCreateView(generics.ListCreateAPIView):
    """List payments, or start a new one.

    With SonicPesa switched on, a mobile-money payment sends a Push USSD to the payer's phone and the
    subscription is extended as soon as they approve it. A 'Control number' payment gets a number from
    ClickPesa that the payer types into mobile money or their bank. 'Manual / Bank' payments (or all
    mobile-money payments, when SonicPesa is off) stay 'pending' until an admin confirms them.
    """

    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly]

    def get_queryset(self):
        return SubscriptionPayment.objects.filter(business=self.request.user.business)

    def perform_create(self, serializer):
        plan = serializer.validated_data['plan']
        payment = serializer.save(business=self.request.user.business, amount=plan.price)
        if payment.provider == SubscriptionPayment.Provider.CONTROL_NUMBER:
            try:
                services.create_control_number(payment)
            except clickpesa.ClickPesaError:
                raise PaymentGatewayError('Could not get a control number. Please try again.')
        elif services.uses_sonicpesa(payment):
            try:
                services.send_push(payment, self.request.user)
            except sonicpesa.SonicPesaError:
                raise PaymentGatewayError()


class SubscriptionPaymentDetailView(generics.RetrieveAPIView):
    """One payment. While it is pending, SonicPesa is asked for the latest status first."""

    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [HasBusiness]

    def get_queryset(self):
        return SubscriptionPayment.objects.filter(business=self.request.user.business)

    def get_object(self):
        return services.refresh_payment(super().get_object())


class SonicPesaWebhookView(APIView):
    """SonicPesa calls this when a payment succeeds or fails. Set its URL in SonicPesa's API Settings page."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Read the raw body before request.data, because the signature is made from the exact bytes sent
        if not sonicpesa.verify_signature(request.body, request.headers.get('X-SonicPesa-Signature', '')):
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        order_id = data.get('order_id')
        payment = SubscriptionPayment.objects.filter(gateway_order_id=order_id).first() if order_id else None
        if payment is None:
            # Not one of our subscription payments (e.g. a payout event). Answer OK so it isn't sent again.
            return Response({'detail': 'Ignored.'})

        services.apply_gateway_status(
            payment,
            data.get('status') or data.get('payment_status'),
            transid=data.get('transid'),
            channel=data.get('channel'),
            amount=data.get('amount'),
        )
        return Response({'detail': 'OK.'})


class ClickPesaWebhookView(APIView):
    """ClickPesa calls this when a control number is paid. Set its URL in ClickPesa's Developers settings."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not clickpesa.verify_checksum(request.data):
            return Response({'detail': 'Invalid checksum.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.get('data')
        if not isinstance(data, dict):
            return Response({'detail': 'Ignored.'})
        # For a control number, ClickPesa sends the control number as the order reference
        numbers = [n for n in (data.get('orderReference'), data.get('paymentReference')) if n]
        payment = SubscriptionPayment.objects.filter(control_number__in=numbers).first() if numbers else None
        if payment is None:
            # Not one of our control numbers (e.g. a payout). Answer OK so it isn't sent again.
            return Response({'detail': 'Ignored.'})

        services.apply_clickpesa_payment(payment, data)
        return Response({'detail': 'OK.'})
