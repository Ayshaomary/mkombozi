from django.db.models import Sum
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from accounts.permissions import HasBusiness, IsOwnerOrCreateOnly, IsOwnerOrReadOnly
from accounts.scoping import BusinessScopedMixin
from reports.dates import date_range_from_params
from subscriptions.permissions import HasActiveSubscription

from .models import ProductionRun, Recipe
from .serializers import ProductionRunSerializer, RecipeSerializer
from .services import cancel_production, record_production


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
