from decimal import Decimal

from rest_framework import serializers

from accounts.scoping import BusinessScopedPrimaryKeyRelatedField
from inventory.models import Product

from .models import ProductionRun, ProductionRunItem, Recipe, RecipeItem

POSITIVE = {'max_digits': 12, 'decimal_places': 2, 'min_value': Decimal('0.01')}


class RecipeItemSerializer(serializers.ModelSerializer):
    material = BusinessScopedPrimaryKeyRelatedField(queryset=Product.objects.all())
    material_name = serializers.CharField(source='material.name', read_only=True)
    unit = serializers.CharField(source='material.unit', read_only=True)
    cost_price = serializers.DecimalField(source='material.cost_price', max_digits=12, decimal_places=2, read_only=True)
    stock_quantity = serializers.DecimalField(
        source='material.stock_quantity', max_digits=12, decimal_places=2, read_only=True
    )
    quantity = serializers.DecimalField(**POSITIVE)

    class Meta:
        model = RecipeItem
        fields = ['id', 'material', 'material_name', 'unit', 'cost_price', 'stock_quantity', 'quantity']


class RecipeSerializer(serializers.ModelSerializer):
    product = BusinessScopedPrimaryKeyRelatedField(queryset=Product.objects.all())
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_unit = serializers.CharField(source='product.unit', read_only=True)
    selling_price = serializers.DecimalField(
        source='product.selling_price', max_digits=12, decimal_places=2, read_only=True
    )
    output_quantity = serializers.DecimalField(**POSITIVE)
    items = RecipeItemSerializer(many=True)
    # At today's buying prices of the materials
    cost_per_batch = serializers.SerializerMethodField()
    cost_per_unit = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            'id', 'product', 'product_name', 'product_unit', 'selling_price', 'output_quantity',
            'note', 'items', 'cost_per_batch', 'cost_per_unit', 'updated_at',
        ]

    def get_cost_per_batch(self, recipe):
        return str(sum((item.material.cost_price * item.quantity for item in recipe.items.all()), Decimal(0)))

    def get_cost_per_unit(self, recipe):
        return str((Decimal(self.get_cost_per_batch(recipe)) / recipe.output_quantity).quantize(Decimal('0.01')))

    def validate(self, attrs):
        product = attrs.get('product', getattr(self.instance, 'product', None))
        items = attrs.get('items')
        if items is not None:
            if not items:
                raise serializers.ValidationError({'items': 'Add at least one material.'})
            materials = [item['material'].pk for item in items]
            if product and product.pk in materials:
                raise serializers.ValidationError({'items': 'A product cannot be made from itself.'})
            if len(materials) != len(set(materials)):
                raise serializers.ValidationError({'items': 'Each material can be listed only once.'})
        if product and 'product' in attrs:
            existing = Recipe.objects.filter(product=product)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({'product': 'This product already has a recipe. Edit that one.'})
        return attrs

    def create(self, validated_data):
        items = validated_data.pop('items')
        recipe = Recipe.objects.create(**validated_data)
        RecipeItem.objects.bulk_create(RecipeItem(recipe=recipe, **item) for item in items)
        return recipe

    def update(self, instance, validated_data):
        items = validated_data.pop('items', None)
        instance = super().update(instance, validated_data)
        if items is not None:
            instance.items.all().delete()
            RecipeItem.objects.bulk_create(RecipeItem(recipe=instance, **item) for item in items)
        return instance


class ProductionRunItemSerializer(serializers.ModelSerializer):
    material = BusinessScopedPrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    quantity = serializers.DecimalField(**POSITIVE)

    class Meta:
        model = ProductionRunItem
        fields = ['id', 'material', 'material_name', 'quantity', 'unit_cost', 'subtotal']
        read_only_fields = ['material_name', 'unit_cost', 'subtotal']


class ProductionRunSerializer(serializers.ModelSerializer):
    product = BusinessScopedPrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    unit = serializers.CharField(source='product.unit', read_only=True, default=None)
    quantity = serializers.DecimalField(**POSITIVE)
    extra_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False)
    items = ProductionRunItemSerializer(many=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = ProductionRun
        fields = [
            'id', 'batch_number', 'product', 'product_name', 'unit', 'quantity', 'materials_cost',
            'extra_cost', 'total_cost', 'unit_cost', 'note', 'produced_at', 'items', 'created_by_name',
            'created_at',
        ]
        read_only_fields = [
            'batch_number', 'product_name', 'materials_cost', 'total_cost', 'unit_cost', 'created_at',
        ]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Add at least one material.')
        return value
