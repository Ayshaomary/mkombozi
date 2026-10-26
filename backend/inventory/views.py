from django.db import transaction
from django.db.models import Count, F, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import HasBusiness, IsOwnerOrReadOnly
from accounts.scoping import BusinessScopedMixin
from subscriptions.permissions import HasActiveSubscription

from .models import Category, Product, StockMovement
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    StockChangeSerializer,
    StockMovementSerializer,
)
from .services import change_stock


class CategoryViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    # Django drops Meta.ordering on queries with Count(), so set the order again
    queryset = Category.objects.annotate(product_count=Count('products')).order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly, HasActiveSubscription]
    pagination_class = None


class ProductViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    """Products of the business.

    Filters: ?search=sugar  ?category=3  ?low_stock=true  ?active=true
    """

    queryset = Product.objects.select_related('category')
    serializer_class = ProductSerializer
    permission_classes = [HasBusiness, IsOwnerOrReadOnly, HasActiveSubscription]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if search := params.get('search'):
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search))
        if category := params.get('category'):
            queryset = queryset.filter(category_id=category)
        if params.get('low_stock') == 'true':
            queryset = queryset.filter(stock_quantity__lte=F('low_stock_threshold'))
        if params.get('active') == 'true':
            queryset = queryset.filter(is_active=True)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        opening_stock = serializer.validated_data.pop('opening_stock', 0)
        super().perform_create(serializer)
        if opening_stock:
            change_stock(
                serializer.instance, opening_stock, StockMovement.Type.OPENING, self.request.user
            )
            serializer.instance.refresh_from_db()

    def perform_update(self, serializer):
        serializer.validated_data.pop('opening_stock', None)
        serializer.save()

    @action(detail=True, methods=['post'])
    def stock(self, request, pk=None):
        """Add stock (purchase, return) or correct it (adjustment). POST /api/products/<id>/stock/"""
        product = self.get_object()
        serializer = StockChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            if 'new_cost_price' in data:
                product.cost_price = data['new_cost_price']
                product.save(update_fields=['cost_price', 'updated_at'])
            product = change_stock(
                product, data['quantity'], data['movement_type'], request.user, data.get('note', '')
            )
        return Response(ProductSerializer(product, context={'request': request}).data)


class StockMovementViewSet(BusinessScopedMixin, viewsets.ReadOnlyModelViewSet):
    """Stock history. Filter by product: ?product=5"""

    queryset = StockMovement.objects.select_related('product', 'created_by')
    serializer_class = StockMovementSerializer
    permission_classes = [HasBusiness]

    def get_queryset(self):
        queryset = super().get_queryset()
        if product := self.request.query_params.get('product'):
            queryset = queryset.filter(product_id=product)
        return queryset
