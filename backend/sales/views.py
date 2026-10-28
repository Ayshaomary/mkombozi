from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from accounts.models import Permission
from accounts.permissions import HasBusiness, can
from accounts.scoping import BusinessScopedMixin, find_by_client_id
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
    permission_classes = [
        HasBusiness, can(create=Permission.SALES, delete=Permission.MANAGE), HasActiveSubscription,
    ]

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
            # Django drops Meta.ordering on queries with Count(), so set the order again
            queryset = queryset.annotate(item_count=Count('items')).order_by(*Sale._meta.ordering)
        else:
            queryset = queryset.prefetch_related('items')
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # The total of ALL matching sales, not just this page
        response.data['total'] = self.get_queryset().aggregate(total=Sum('total_amount'))['total'] or 0
        return response

    def create(self, request, *args, **kwargs):
        # A phone that lost the network may send the same sale again: answer with the one already saved
        if existing := find_by_client_id(self.get_queryset(), request.data.get('client_id')):
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop('items')
        try:
            sale = create_sale(request.user.business, request.user, items, **data)
        except IntegrityError:
            # The same sale arrived twice at the same moment; the other request saved it
            existing = find_by_client_id(self.get_queryset(), data.get('client_id'))
            if existing is None:
                raise
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        return Response(self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        cancel_sale(instance, self.request.user)
