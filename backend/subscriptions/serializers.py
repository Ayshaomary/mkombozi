import re

from rest_framework import serializers

from accounts.serializers import clean_phone

from . import clickpesa
from .models import NETWORK_PREFIXES, Plan, Subscription, SubscriptionPayment


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
            'reference', 'control_number', 'status', 'push_sent', 'created_at', 'completed_at',
        ]
        read_only_fields = ['amount', 'reference', 'control_number', 'status', 'created_at', 'completed_at']

    def get_push_sent(self, payment):
        return bool(payment.gateway_order_id)

    def validate_phone(self, value):
        return clean_phone(value)

    def validate(self, attrs):
        provider = attrs.get('provider')
        if provider == SubscriptionPayment.Provider.CONTROL_NUMBER:
            if not clickpesa.is_enabled():
                raise serializers.ValidationError({'provider': 'Paying by control number is not available yet.'})
            # Anyone can pay a control number from any phone, so no number is needed
            attrs['phone'] = ''
            return attrs
        if provider == SubscriptionPayment.Provider.MANUAL:
            if not attrs.get('phone'):
                raise serializers.ValidationError({'phone': 'Enter the phone number you paid from.'})
            return attrs
        # Mobile money needs a Tanzanian number from the chosen network, e.g. M-Pesa: 074...
        match = re.fullmatch(r'\+255(\d{2})\d{7}', attrs.get('phone', ''))
        if not match:
            raise serializers.ValidationError({'phone': 'Enter a Tanzanian mobile number, e.g. 0742 345 678.'})
        prefixes = NETWORK_PREFIXES.get(provider, ())
        if '0' + match.group(1) not in prefixes:
            network = SubscriptionPayment.Provider(provider).label
            raise serializers.ValidationError(
                {'phone': f'This number is not on {network}. Use a number starting with {", ".join(prefixes)}.'}
            )
        return attrs
