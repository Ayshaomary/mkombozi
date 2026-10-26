from django.contrib import admin, messages

from .models import Plan, Subscription, SubscriptionPayment


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'price', 'duration_days', 'is_active', 'sort_order']
    list_editable = ['is_active', 'sort_order']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['business', 'status', 'plan', 'current_period_end']
    list_filter = ['status', 'plan']
    search_fields = ['business__name']


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'business', 'plan', 'amount', 'provider', 'phone', 'status', 'created_at']
    list_filter = ['status', 'provider']
    search_fields = ['reference', 'business__name', 'phone']
    readonly_fields = ['reference', 'completed_at']
    actions = ['confirm_payments']

    @admin.action(description='Confirm selected payments (extends subscription)')
    def confirm_payments(self, request, queryset):
        count = 0
        for payment in queryset.exclude(status=SubscriptionPayment.Status.COMPLETED):
            payment.mark_completed()
            count += 1
        self.message_user(request, f'{count} payment(s) confirmed.', messages.SUCCESS)
