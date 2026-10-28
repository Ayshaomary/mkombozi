from django.db import IntegrityError
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response

from accounts.permissions import HasBusiness, IsOwner, IsOwnerOrCreateOnly
from accounts.scoping import BusinessScopedMixin, find_by_client_id
from reports.dates import date_range_from_params
from subscriptions.permissions import HasActiveSubscription

from .models import Expense, RecurringExpense
from .serializers import ExpenseSerializer, RecurringExpenseSerializer
from .services import process_recurring_expenses


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

    def create(self, request, *args, **kwargs):
        # A phone that lost the network may send the same expense again: answer with the one already saved
        if existing := find_by_client_id(self.get_queryset(), request.data.get('client_id')):
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            existing = find_by_client_id(self.get_queryset(), request.data.get('client_id'))
            if existing is None:
                raise
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # The total of ALL matching expenses, not just this page
        response.data['total'] = self.get_queryset().aggregate(total=Sum('amount'))['total'] or 0
        return response


class RecurringExpenseViewSet(BusinessScopedMixin, viewsets.ModelViewSet):
    """Expenses that repeat (rent, salaries...). Only the owner manages them."""

    queryset = RecurringExpense.objects.all()
    serializer_class = RecurringExpenseSerializer
    permission_classes = [HasBusiness, IsOwner, HasActiveSubscription]
    pagination_class = None

    def perform_create(self, serializer):
        super().perform_create(serializer)
        # If it's already due (e.g. starts today), record it straight away
        recurring = serializer.instance
        process_recurring_expenses(
            recurring.business, timezone.localdate(), RecurringExpense.objects.filter(pk=recurring.pk)
        )
        recurring.refresh_from_db()
