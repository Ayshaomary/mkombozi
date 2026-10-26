from django.contrib import admin

from .models import Category, Product, StockMovement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'business']
    search_fields = ['name', 'business__name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'category', 'selling_price', 'stock_quantity', 'is_active']
    list_filter = ['is_active', 'unit']
    search_fields = ['name', 'sku', 'business__name']
    readonly_fields = ['stock_quantity']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'business', 'movement_type', 'quantity', 'stock_after', 'created_at']
    list_filter = ['movement_type']
    search_fields = ['product__name', 'business__name']
