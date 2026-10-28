from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Permission
from accounts.permissions import HasBusiness, can
from sales.models import Sale
from sales.serializers import SaleListSerializer

from . import services
from .dates import date_range_from_params


class DashboardView(APIView):
    """Everything the home screen needs in one request."""

    permission_classes = [HasBusiness, can(read=Permission.REPORTS)]

    def get(self, request):
        business = request.user.business
        today = timezone.localdate()
        month_start = today.replace(day=1)
        week_start = today - timedelta(days=6)
        recent = Sale.objects.filter(business=business).select_related('created_by')[:5]
        return Response({
            'today': services.totals(business, today, today),
            'month': services.totals(business, month_start, today),
            'last_7_days': services.daily_series(business, week_start, today),
            'stock': services.stock_summary(business),
            'recent_sales': SaleListSerializer(recent, many=True).data,
        })


class SummaryReportView(APIView):
    """Profit & loss report. ?period=today|week|month|year or ?start=YYYY-MM-DD&end=YYYY-MM-DD"""

    permission_classes = [HasBusiness, can(read=Permission.REPORTS)]

    def get(self, request):
        business = request.user.business
        start, end = date_range_from_params(request.query_params, default='month')
        today = timezone.localdate()
        start = start or end or today
        end = end or today
        return Response({
            'start': start,
            'end': end,
            'totals': services.totals(business, start, end),
            'daily': services.daily_series(business, start, end),
            'top_products': services.top_products(business, start, end),
            'payment_methods': services.payment_methods(business, start, end),
            'expenses_by_category': services.expenses_by_category(business, start, end),
        })
