from django.contrib import admin

from .models import ProductionRun, ProductionRunItem, Recipe, RecipeItem


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['product', 'business', 'output_quantity', 'updated_at']
    search_fields = ['product__name', 'business__name']
    inlines = [RecipeItemInline]


class ProductionRunItemInline(admin.TabularInline):
    model = ProductionRunItem
    extra = 0
    readonly_fields = ['material', 'material_name', 'quantity', 'unit_cost', 'subtotal']
    can_delete = False


@admin.register(ProductionRun)
class ProductionRunAdmin(admin.ModelAdmin):
    list_display = ['batch_number', 'business', 'product_name', 'quantity', 'total_cost', 'unit_cost', 'produced_at']
    list_filter = ['business']
    search_fields = ['batch_number', 'product_name', 'business__name']
    readonly_fields = [
        'batch_number', 'product', 'product_name', 'quantity', 'materials_cost', 'extra_cost',
        'total_cost', 'unit_cost', 'created_by', 'created_at',
    ]
    inlines = [ProductionRunItemInline]
