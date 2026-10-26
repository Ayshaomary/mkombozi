from django.db.models import Sum
from rest_framework import viewsets

from accounts.permissions import HasBusiness, IsOwnerOrCreateOnly
from accounts.scoping import BusinessScopedMixin
from reports.dates import date_range_from_params
from subscriptions.permissions import HasActiveSubscription

from .models import Expense
from .serializers import ExpenseSerializer


class ExpenseViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    """Filters: ?period=month  or  ?start=2026-10-01&end=2026-10-31,  ?category=rent"""

    queryset = Expense.objects.select_related('created_by')
    serializer_class = ExpenseSerializer
    permission_classes = [HasBusiness, IsOwnerOrCreateOnly, HasActiveSubscription]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            params = self.request.query_params
            start, end = date_range_from_params(params)
            if start:
                queryset = queryset.filter(date__gte=start)
            if end:
                queryset = queryset.filter(date__lte=end)
            if category := params.get('category'):
                queryset = queryset.filter(category=category)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # The total of ALL matching expenses, not just this page
        response.data['total'] = self.get_queryset().aggregate(total=Sum('amount'))['total'] or 0
        return response
