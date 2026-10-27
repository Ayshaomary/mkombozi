from django.contrib import admin, messages

from . import services
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
    search_fields = ['reference', 'business__name', 'phone', 'gateway_order_id', 'gateway_transid']
    readonly_fields = ['reference', 'gateway_order_id', 'gateway_transid', 'failure_reason', 'completed_at']
    actions = ['confirm_payments', 'check_sonicpesa']

    @admin.action(description='Confirm selected payments (extends subscription)')
    def confirm_payments(self, request, queryset):
        count = 0
        for payment in queryset.exclude(status=SubscriptionPayment.Status.COMPLETED):
            payment.mark_completed()
            count += 1
        self.message_user(request, f'{count} payment(s) confirmed.', messages.SUCCESS)

    @admin.action(description='Check status with SonicPesa')
    def check_sonicpesa(self, request, queryset):
        pending = queryset.filter(status=SubscriptionPayment.Status.PENDING).exclude(gateway_order_id='')
        results = [services.refresh_payment(payment).status for payment in pending]
        completed = results.count(SubscriptionPayment.Status.COMPLETED)
        failed = results.count(SubscriptionPayment.Status.FAILED)
        self.message_user(
            request,
            f'Checked {len(results)}: {completed} completed, {failed} failed, '
            f'{len(results) - completed - failed} still pending.',
            messages.INFO,
        )
