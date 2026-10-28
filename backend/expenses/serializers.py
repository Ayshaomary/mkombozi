from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Expense, RecurringExpense


class ExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    is_recurring = serializers.SerializerMethodField()
    # Sent by phones that record expenses offline (see expenses.views.ExpenseViewSet.create)
    client_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'category', 'category_display', 'amount', 'description', 'date',
            'is_recurring', 'created_by_name', 'created_at', 'client_id',
        ]
        read_only_fields = ['created_at']

    def get_is_recurring(self, expense):
        return expense.recurring_id is not None


class RecurringExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    class Meta:
        model = RecurringExpense
        fields = [
            'id', 'category', 'amount', 'description', 'frequency', 'start_date',
            'next_date', 'occurrences', 'is_active', 'created_at',
        ]
        read_only_fields = ['next_date', 'occurrences', 'created_at']

    def validate_start_date(self, value):
        # Limit how far back missed expenses are filled in
        if value < timezone.localdate() - timedelta(days=366):
            raise serializers.ValidationError('Start date cannot be more than a year ago.')
        return value

    def update(self, instance, validated_data):
        # Changing when it repeats would confuse the expenses already recorded:
        # delete it and create a new one instead
        validated_data.pop('frequency', None)
        validated_data.pop('start_date', None)
        return super().update(instance, validated_data)
