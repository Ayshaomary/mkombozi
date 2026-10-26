from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from subscriptions.models import Subscription

from .models import Business, User
from .utils import normalize_phone


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'phone', 'location', 'created_at']
        read_only_fields = ['created_at']

    def validate_phone(self, value):
        return normalize_phone(value)


class UserSerializer(serializers.ModelSerializer):
    business = BusinessSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'phone', 'first_name', 'last_name', 'role', 'business']
        read_only_fields = ['phone', 'role']


class PhoneField(serializers.CharField):
    """A phone number field that stores numbers in one standard format."""

    def to_internal_value(self, data):
        phone = normalize_phone(super().to_internal_value(data))
        if len(phone) < 9:
            raise serializers.ValidationError('Enter a valid phone number.')
        return phone


class RegisterSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=150)
    business_location = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = PhoneField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('An account with this phone number already exists.')
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        business = Business.objects.create(
            name=validated_data['business_name'],
            location=validated_data.get('business_location', ''),
            phone=validated_data['phone'],
        )
        Subscription.start_trial(business)
        return User.objects.create_user(
            phone=validated_data['phone'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', ''),
            business=business,
            role=User.Role.OWNER,
        )


class LoginSerializer(TokenObtainPairSerializer):
    """Login with phone + password. Also returns the user's details."""

    def validate(self, attrs):
        attrs[self.username_field] = normalize_phone(attrs.get(self.username_field))
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class StaffSerializer(serializers.ModelSerializer):
    phone = PhoneField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'phone', 'first_name', 'last_name', 'role', 'password', 'date_joined']
        read_only_fields = ['role', 'date_joined']

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError('An account with this phone number already exists.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(role=User.Role.STAFF, **validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context['request'].user)
        return value
