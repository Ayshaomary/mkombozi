from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['product', 'product_name', 'quantity', 'unit_price', 'unit_cost', 'subtotal']
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'business', 'total_amount', 'payment_method', 'sold_at']
    list_filter = ['payment_method']
    search_fields = ['receipt_number', 'customer_name', 'business__name']
    inlines = [SaleItemInline]
    readonly_fields = ['total_amount', 'total_cost']
