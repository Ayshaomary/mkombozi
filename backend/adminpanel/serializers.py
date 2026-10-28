from rest_framework import serializers

from accounts.models import User
from activity.models import ActivityLog


class AdminActivitySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.CharField(source='user.phone', default=None, read_only=True)
    business_name = serializers.CharField(source='business.name', default=None, read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'created_at', 'user', 'user_name', 'user_phone', 'business', 'business_name',
            'action', 'summary', 'ip_address',
        ]

    def get_user_name(self, entry):
        return entry.user.get_full_name() if entry.user else None


class AdminUserSerializer(serializers.ModelSerializer):
    """A user as admins see and edit them. Only role, active and admin access can be changed."""

    business_name = serializers.CharField(source='business.name', default=None, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'phone', 'first_name', 'last_name', 'business', 'business_name', 'role',
            'is_active', 'is_staff', 'is_superuser', 'date_joined', 'avatar_key',
        ]
        read_only_fields = [
            'phone', 'first_name', 'last_name', 'business', 'is_superuser', 'date_joined', 'avatar_key',
        ]

    def validate(self, attrs):
        admin = self.context['request'].user
        user = self.instance

        if user.is_superuser and not admin.is_superuser:
            raise serializers.ValidationError('Only a superuser can change another superuser.')
        if 'is_staff' in attrs and attrs['is_staff'] != user.is_staff and not admin.is_superuser:
            raise serializers.ValidationError({'is_staff': 'Only a superuser can give or remove admin access.'})
        if user == admin and (attrs.get('is_active') is False or attrs.get('is_staff') is False):
            # Stops an admin from locking themselves out by mistake
            raise serializers.ValidationError("You can't remove your own access.")

        # A shop must keep at least one active owner, or nobody could manage it or pay for it
        stays_owner = attrs.get('role', user.role) == User.Role.OWNER and attrs.get('is_active', user.is_active)
        was_owner = user.role == User.Role.OWNER and user.is_active
        if user.business_id and was_owner and not stays_owner:
            other_owners = User.objects.filter(
                business_id=user.business_id, role=User.Role.OWNER, is_active=True
            ).exclude(pk=user.pk)
            if not other_owners.exists():
                raise serializers.ValidationError(
                    'This shop needs at least one active owner. Make another user owner first.'
                )
        return attrs
