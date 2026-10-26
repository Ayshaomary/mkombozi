from decimal import Decimal

from rest_framework import serializers

from accounts.scoping import BusinessScopedPrimaryKeyRelatedField
from accounts.utils import normalize_phone
from inventory.models import Product

from .models import Sale, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    product = BusinessScopedPrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False,
        help_text="Leave empty to use the product's selling price.",
    )

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'unit_cost', 'subtotal']
        read_only_fields = ['product_name', 'unit_cost', 'subtotal']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False)

    class Meta:
        model = Sale
        fields = [
            'id', 'receipt_number', 'customer_name', 'customer_phone', 'payment_method',
            'payment_method_display', 'discount', 'total_amount', 'total_cost', 'profit',
            'note', 'sold_at', 'items', 'created_by_name', 'created_at',
        ]
        read_only_fields = ['receipt_number', 'total_amount', 'total_cost', 'created_at']

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Add at least one product to the sale.')
        return value

    def validate_customer_phone(self, value):
        return normalize_phone(value) if value else value


class SaleListSerializer(serializers.ModelSerializer):
    """Lighter version for lists: no item details."""

    profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Sale
        fields = [
            'id', 'receipt_number', 'customer_name', 'payment_method', 'payment_method_display',
            'total_amount', 'profit', 'item_count', 'sold_at', 'created_by_name',
        ]
