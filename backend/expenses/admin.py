from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'business', 'category', 'amount', 'description']
    list_filter = ['category']
    search_fields = ['description', 'business__name']
