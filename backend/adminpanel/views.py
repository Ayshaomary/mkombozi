"""The admin dashboard in the app: numbers for the whole platform, everyone's activity, and all users.

Only admins (users with "Staff status" in the Django admin) can use these endpoints.
"""

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Business, User
from activity.models import ActivityLog
from activity.services import record
from subscriptions.models import Subscription, SubscriptionPayment

from .serializers import AdminActivitySerializer, AdminUserSerializer

YES_NO = {True: 'yes', False: 'no'}


class OverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        day_ago = now - timedelta(days=1)
        month_start = now.astimezone(timezone.get_current_timezone()).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        valid = Q(current_period_end__gt=now) & ~Q(status=Subscription.Status.CANCELLED)
        completed = SubscriptionPayment.objects.filter(status=SubscriptionPayment.Status.COMPLETED)

        return Response({
            'businesses': Business.objects.count(),
            'new_businesses_week': Business.objects.filter(created_at__gte=week_ago).count(),
            'users': User.objects.filter(business__isnull=False).count(),
            'active_users_month': ActivityLog.objects.filter(
                action=ActivityLog.Action.LOGIN, created_at__gte=now - timedelta(days=30)
            ).values('user').distinct().count(),
            'subscriptions': {
                'trial': Subscription.objects.filter(valid, status=Subscription.Status.TRIAL).count(),
                'active': Subscription.objects.filter(valid, status=Subscription.Status.ACTIVE).count(),
                'expired': Subscription.objects.exclude(valid).count(),
            },
            'revenue_month': completed.filter(completed_at__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0,
            'revenue_total': completed.aggregate(s=Sum('amount'))['s'] or 0,
            'pending_payments': SubscriptionPayment.objects.filter(status=SubscriptionPayment.Status.PENDING).count(),
            'activities_today': ActivityLog.objects.filter(created_at__gte=day_ago).count(),
            'failed_logins_today': ActivityLog.objects.filter(
                action=ActivityLog.Action.LOGIN_FAILED, created_at__gte=day_ago
            ).count(),
            'business_types': list(
                Business.objects.values('business_type').annotate(count=Count('id')).order_by('-count')
            ),
            'recent_businesses': [
                {
                    'id': b.id, 'name': b.name, 'business_type': b.business_type,
                    'location': b.location, 'created_at': b.created_at,
                }
                for b in Business.objects.order_by('-created_at')[:5]
            ],
        })


class ActivityListView(generics.ListAPIView):
    """Everyone's activity, newest first. Filters: ?search= ?action= ?business= ?user="""

    serializer_class = AdminActivitySerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user', 'business')
        params = self.request.query_params
        if search := params.get('search', '').strip():
            queryset = queryset.filter(
                Q(summary__icontains=search) | Q(user__phone__icontains=search)
                | Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search)
                | Q(business__name__icontains=search) | Q(ip_address__startswith=search)
            )
        for field in ('action', 'business', 'user'):
            if value := params.get(field):
                queryset = queryset.filter(**{field: value})
        return queryset


class UserListView(generics.ListAPIView):
    """All users. Filters: ?search= ?role=owner|staff|admin ?business="""

    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = User.objects.select_related('business').order_by('-date_joined')
        params = self.request.query_params
        if search := params.get('search', '').strip():
            queryset = queryset.filter(
                Q(phone__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(business__name__icontains=search)
            )
        role = params.get('role')
        if role == 'admin':
            queryset = queryset.filter(is_staff=True)
        elif role in User.Role.values:
            queryset = queryset.filter(role=role, business__isnull=False)
        if business := params.get('business'):
            queryset = queryset.filter(business=business)
        return queryset


class UserUpdateView(generics.UpdateAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.select_related('business')
    http_method_names = ['patch']

    def perform_update(self, serializer):
        user = serializer.instance
        before = {'role': user.role, 'is_active': user.is_active, 'is_staff': user.is_staff}
        user = serializer.save()
        changes = []
        if before['role'] != user.role:
            changes.append(f'role {before["role"]} → {user.role}')
        if before['is_active'] != user.is_active:
            changes.append(f'active {YES_NO[before["is_active"]]} → {YES_NO[user.is_active]}')
        if before['is_staff'] != user.is_staff:
            changes.append(f'admin {YES_NO[before["is_staff"]]} → {YES_NO[user.is_staff]}')
        if changes:
            record(
                self.request, self.request.user, ActivityLog.Action.UPDATE,
                f'Admin changed {user.get_full_name() or user.phone} ({user.phone}): {", ".join(changes)}',
            )


class BusinessListView(generics.ListAPIView):
    """Every business's id and name, for the filters."""

    permission_classes = [permissions.IsAdminUser]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response(list(Business.objects.order_by('name').values('id', 'name')))
