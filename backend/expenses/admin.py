from django.contrib import admin

from .models import Expense, RecurringExpense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'business', 'category', 'amount', 'description', 'recurring']
    list_filter = ['category']
    search_fields = ['description', 'business__name']


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ['business', 'category', 'amount', 'frequency', 'next_date', 'occurrences', 'is_active']
    list_filter = ['frequency', 'is_active']
    search_fields = ['description', 'business__name']
    readonly_fields = ['next_date', 'occurrences']
