from rest_framework import serializers

from accounts.utils import normalize_phone

from .models import Plan, Subscription, SubscriptionPayment


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'code', 'name', 'price', 'duration_days', 'description']


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    days_left = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = ['status', 'plan', 'current_period_end', 'is_valid', 'days_left']


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.filter(is_active=True))
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'plan', 'plan_name', 'amount', 'phone', 'provider',
            'reference', 'status', 'created_at', 'completed_at',
        ]
        read_only_fields = ['amount', 'reference', 'status', 'created_at', 'completed_at']

    def validate_phone(self, value):
        return normalize_phone(value)
