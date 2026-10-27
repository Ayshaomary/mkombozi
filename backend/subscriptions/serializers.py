import re

from rest_framework import serializers

from accounts.utils import normalize_phone

from . import sonicpesa
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
    # True when a Push USSD was sent, so the app can wait for the payer to approve it on their phone
    push_sent = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'plan', 'plan_name', 'amount', 'phone', 'provider',
            'reference', 'status', 'push_sent', 'created_at', 'completed_at',
        ]
        read_only_fields = ['amount', 'reference', 'status', 'created_at', 'completed_at']

    def get_push_sent(self, payment):
        return bool(payment.gateway_order_id)

    def validate_phone(self, value):
        return normalize_phone(value)

    def validate(self, attrs):
        # Mobile money needs a real Tanzanian number, e.g. 0712 345 678
        mobile = attrs.get('provider') != SubscriptionPayment.Provider.MANUAL
        if mobile and sonicpesa.is_enabled() and not re.fullmatch(r'\+255[67]\d{8}', attrs.get('phone', '')):
            raise serializers.ValidationError({'phone': 'Enter a Tanzanian mobile number, e.g. 0712 345 678.'})
        return attrs
