from decimal import Decimal

from rest_framework import serializers

from accounts.scoping import BusinessScopedPrimaryKeyRelatedField
from inventory.models import Product

from .models import ProductionRun, ProductionRunItem, Recipe, RecipeItem
from .services import create_material, find_material

POSITIVE = {'max_digits': 12, 'decimal_places': 2, 'min_value': Decimal('0.01')}


class TypedMaterialMixin(serializers.Serializer):
    """A material line can name a material instead of choosing one: an existing product with that
    name is used, or a new raw material is made with the typed unit and price."""

    name = serializers.CharField(max_length=150, required=False, write_only=True)
    new_unit = serializers.ChoiceField(choices=Product.Unit.choices, required=False, write_only=True)
    new_unit_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False, write_only=True,
        help_text='Buying price per unit, for a material the business did not have yet.',
    )

    def validate(self, attrs):
        if not attrs.get('material') and not (attrs.get('name') or '').strip():
            raise serializers.ValidationError('Choose a material or type its name.')
        # The names production.services uses
        attrs['unit'] = attrs.pop('new_unit', None)
        attrs['unit_cost'] = attrs.pop('new_unit_cost', None)
        return attrs


class RecipeItemSerializer(TypedMaterialMixin, serializers.ModelSerializer):
    material = BusinessScopedPrimaryKeyRelatedField(queryset=Product.objects.all(), required=False, allow_null=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    unit = serializers.CharField(source='material.unit', read_only=True)
    cost_price = serializers.DecimalField(source='material.cost_price', max_digits=12, decimal_places=2, read_only=True)
    stock_quantity = serializers.DecimalField(
        source='material.stock_quantity', max_digits=12, decimal_places=2, read_only=True
    )
    quantity = serializers.DecimalField(**POSITIVE)

    class Meta:
        model = RecipeItem
        fields = [
            'id', 'material', 'material_name', 'unit', 'cost_price', 'stock_quantity', 'quantity',
            'name', 'new_unit', 'new_unit_cost',
        ]


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
            business = self.context['request'].user.business
            for item in items:
                # A typed name that the business already has is that product
                if not item.get('material'):
                    item['material'] = find_material(business, item['name'])
            if product and any(item['material'] == product for item in items):
                raise serializers.ValidationError({'items': 'A product cannot be made from itself.'})
            keys = [item['material'].pk if item['material'] else item['name'].strip().lower() for item in items]
            if len(keys) != len(set(keys)):
                raise serializers.ValidationError({'items': 'Each material can be listed only once.'})
        if product and 'product' in attrs:
            existing = Recipe.objects.filter(product=product)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({'product': 'This product already has a recipe. Edit that one.'})
        return attrs

    def save_items(self, recipe, items):
        recipe.items.all().delete()
        RecipeItem.objects.bulk_create(
            RecipeItem(
                recipe=recipe,
                # A material typed by name that the business didn't have yet becomes a new raw material
                material=item['material']
                or create_material(recipe.business, item['name'], item['unit'], item['unit_cost']),
                quantity=item['quantity'],
            )
            for item in items
        )

    def create(self, validated_data):
        items = validated_data.pop('items')
        recipe = Recipe.objects.create(**validated_data)
        self.save_items(recipe, items)
        return recipe

    def update(self, instance, validated_data):
        items = validated_data.pop('items', None)
        instance = super().update(instance, validated_data)
        if items is not None:
            self.save_items(instance, items)
        return instance


class ProductionRunItemSerializer(TypedMaterialMixin, serializers.ModelSerializer):
    material = BusinessScopedPrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), required=False, allow_null=True
    )
    quantity = serializers.DecimalField(**POSITIVE)

    class Meta:
        model = ProductionRunItem
        fields = [
            'id', 'material', 'material_name', 'quantity', 'unit_cost', 'subtotal',
            'name', 'new_unit', 'new_unit_cost',
        ]
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
