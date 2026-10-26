from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasBusiness, IsOwnerOrReadOnly

from .models import Plan, Subscription, SubscriptionPayment
from .serializers import PlanSerializer, SubscriptionPaymentSerializer, SubscriptionSerializer


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
        return Response(SubscriptionSerializer(subscription).data)


class SubscriptionPaymentListCreateView(generics.ListCreateAPIView):
    """List payments, or start a new one.

    Mobile-money integration (e.g. via a payment aggregator) will go here later. For now a payment
    is saved as 'pending' and an admin confirms it in the Django admin, which extends the subscription.
    """

    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly]

    def get_queryset(self):
        return SubscriptionPayment.objects.filter(business=self.request.user.business)

    def perform_create(self, serializer):
        plan = serializer.validated_data['plan']
        serializer.save(business=self.request.user.business, amount=plan.price)
