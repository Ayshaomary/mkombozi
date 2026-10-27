from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import HasBusiness

from .automations import run_automations
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Notifications for the bell icon. Staff only see notifications meant for everyone.

    Opening this list also runs the automatic tasks if they haven't run in the last few minutes.
    """

    serializer_class = NotificationSerializer
    permission_classes = [HasBusiness]

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(business=user.business)
        if not user.is_owner:
            queryset = queryset.filter(audience=Notification.Audience.ALL)
        return queryset

    def list(self, request, *args, **kwargs):
        run_automations(request.user.business)
        response = super().list(request, *args, **kwargs)
        response.data['unread_count'] = self.get_queryset().filter(read_at__isnull=True).count()
        return response

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({'marked_read': updated})
