from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'kind', 'data', 'created_at', 'is_read']

    def get_is_read(self, notification):
        return notification.read_at is not None
