from django.db.models import Count, Q
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from accounts.permissions import HasBusiness, IsOwnerOrCreateOnly
from accounts.scoping import BusinessScopedMixin
from reports.dates import date_range_from_params
from subscriptions.permissions import HasActiveSubscription

from .models import Sale
from .serializers import SaleListSerializer, SaleSerializer
from .services import cancel_sale, create_sale


class SaleViewSet(
    BusinessScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Sales cannot be edited. To fix a mistake, the owner deletes the sale (stock goes back) and records it again.

    Filters: ?period=today|week|month|year  or  ?start=2026-10-01&end=2026-10-31
             ?payment_method=mpesa  ?search=R00012 (receipt or customer name)
    """

    queryset = Sale.objects.select_related('created_by')
    permission_classes = [HasBusiness, IsOwnerOrCreateOnly, HasActiveSubscription]

    def get_serializer_class(self):
        return SaleListSerializer if self.action == 'list' else SaleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            params = self.request.query_params
            start, end = date_range_from_params(params)
            if start:
                queryset = queryset.filter(sold_at__date__gte=start)
            if end:
                queryset = queryset.filter(sold_at__date__lte=end)
            if method := params.get('payment_method'):
                queryset = queryset.filter(payment_method=method)
            if search := params.get('search'):
                queryset = queryset.filter(
                    Q(receipt_number__icontains=search) | Q(customer_name__icontains=search)
                )
            queryset = queryset.annotate(item_count=Count('items'))
        else:
            queryset = queryset.prefetch_related('items')
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop('items')
        sale = create_sale(request.user.business, request.user, items, **data)
        return Response(self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        cancel_sale(instance, self.request.user)
