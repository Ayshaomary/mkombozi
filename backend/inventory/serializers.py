from decimal import Decimal

from rest_framework import serializers

from accounts.scoping import BusinessScopedPrimaryKeyRelatedField

from .models import Category, Product, StockMovement


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'product_count']

    def validate_name(self, value):
        business = self.context['request'].user.business
        existing = Category.objects.filter(business=business, name__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError('You already have a category with this name.')
        return value


class ProductSerializer(serializers.ModelSerializer):
    category = BusinessScopedPrimaryKeyRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    is_low_stock = serializers.BooleanField(read_only=True)
    opening_stock = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False,
        min_value=Decimal('0'), help_text='Stock you already have when adding the product.',
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'category', 'category_name', 'unit',
            'cost_price', 'selling_price', 'stock_quantity', 'low_stock_threshold',
            'is_low_stock', 'is_active', 'opening_stock', 'created_at', 'updated_at',
        ]
        # Stock only changes through sales and stock movements, never by editing the product
        read_only_fields = ['stock_quantity', 'created_at', 'updated_at']

    def validate(self, attrs):
        cost = attrs.get('cost_price', getattr(self.instance, 'cost_price', None))
        price = attrs.get('selling_price', getattr(self.instance, 'selling_price', None))
        for field, value in (('cost_price', cost), ('selling_price', price)):
            if value is not None and value < 0:
                raise serializers.ValidationError({field: 'Price cannot be negative.'})
        return attrs


class StockChangeSerializer(serializers.Serializer):
    """Input for adding or removing stock by hand (not through a sale)."""

    ALLOWED_TYPES = [
        StockMovement.Type.PURCHASE,
        StockMovement.Type.RETURN,
        StockMovement.Type.ADJUSTMENT,
    ]

    movement_type = serializers.ChoiceField(choices=ALLOWED_TYPES)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    new_cost_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal('0'),
        help_text='Optional: update the buying price when receiving new stock.',
    )

    def validate(self, attrs):
        quantity = attrs['quantity']
        if quantity == 0:
            raise serializers.ValidationError({'quantity': 'Quantity cannot be zero.'})
        # Only adjustments may remove stock (e.g. damaged or lost items)
        if attrs['movement_type'] != StockMovement.Type.ADJUSTMENT and quantity < 0:
            raise serializers.ValidationError({'quantity': 'Quantity must be more than zero.'})
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'movement_type', 'movement_type_display',
            'quantity', 'stock_after', 'note', 'created_by_name', 'created_at',
        ]
