from datetime import timedelta

from django.db.models import Count, F, Max, Q, Sum
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import HasBusiness, IsOwnerOrCreateOnly, IsOwnerOrReadOnly
from accounts.scoping import BusinessScopedMixin
from inventory.models import Product
from reports.dates import date_range_from_params
from subscriptions.permissions import HasActiveSubscription

from .models import ProductionRun, Recipe
from .serializers import ProductionRunSerializer, RecipeSerializer
from .services import cancel_production, record_production


# How far back "most used" materials are counted
USAGE_DAYS = 60


class RecipeViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    """What goes into each product the business makes. Only the owner manages recipes."""

    queryset = Recipe.objects.select_related('product').prefetch_related('items__material')
    serializer_class = RecipeSerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly, HasActiveSubscription]
    pagination_class = None


class ProductionRunViewSet(
    BusinessScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Batches made. Staff can record them; only the owner can cancel one (stock goes back).

    Filters: ?period=today|week|month|year  or  ?start=2026-10-01&end=2026-10-31,  ?product=12
    """

    queryset = ProductionRun.objects.select_related('product', 'created_by').prefetch_related('items')
    serializer_class = ProductionRunSerializer
    permission_classes = [HasBusiness, IsOwnerOrCreateOnly, HasActiveSubscription]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            params = self.request.query_params
            start, end = date_range_from_params(params)
            if start:
                queryset = queryset.filter(produced_at__date__gte=start)
            if end:
                queryset = queryset.filter(produced_at__date__lte=end)
            if product := params.get('product'):
                queryset = queryset.filter(product_id=product)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # The cost of ALL matching batches, not just this page
        response.data['total'] = self.get_queryset().aggregate(total=Sum('total_cost'))['total'] or 0
        return response

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        run = record_production(
            request.user.business,
            request.user,
            data.pop('product'),
            data.pop('quantity'),
            data.pop('items'),
            **data,
        )
        return Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        cancel_production(instance, self.request.user)

    @action(detail=False)
    def materials(self, request):
        """Products to choose from when making something, the ones used most lately first.

        GET /api/production/materials/ -> every active product, with how often it was used in the
        last 60 days. Then raw materials, then the rest, by name.
        """
        since = timezone.now() - timedelta(days=USAGE_DAYS)
        products = (
            Product.objects.filter(business=request.user.business, is_active=True)
            .annotate(
                times_used=Count('production_uses', filter=Q(production_uses__run__produced_at__gte=since)),
                last_used=Max('production_uses__run__produced_at'),
            )
            # Never-used products have no last_used; put them after the ones used before
            .order_by('-times_used', F('last_used').desc(nulls_last=True), '-is_material', 'name')
        )
        return Response([
            {
                'id': p.id, 'name': p.name, 'unit': p.unit, 'cost_price': p.cost_price,
                'selling_price': p.selling_price, 'stock_quantity': p.stock_quantity,
                'low_stock_threshold': p.low_stock_threshold, 'is_low_stock': p.is_low_stock,
                'is_material': p.is_material, 'times_used': p.times_used,
            }
            for p in products
        ])
