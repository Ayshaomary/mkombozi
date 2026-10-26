from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce, TruncDate

from expenses.models import Expense
from inventory.models import Product
from sales.models import PaymentMethod, Sale, SaleItem

ZERO = Decimal('0')
MONEY = DecimalField(max_digits=14, decimal_places=2)


def _sum(field):
    return Coalesce(Sum(field), ZERO, output_field=MONEY)


def sales_in_range(business, start, end):
    return Sale.objects.filter(business=business, sold_at__date__gte=start, sold_at__date__lte=end)


def expenses_in_range(business, start, end):
    return Expense.objects.filter(business=business, date__gte=start, date__lte=end)


def totals(business, start, end):
    """The key numbers for a period: sales, cost of goods sold, expenses and profit."""
    sales = sales_in_range(business, start, end).aggregate(
        count=Count('id'),
        revenue=_sum('total_amount'),
        cost_of_goods=_sum('total_cost'),
        discounts=_sum('discount'),
    )
    expenses_total = expenses_in_range(business, start, end).aggregate(total=_sum('amount'))['total']
    gross_profit = sales['revenue'] - sales['cost_of_goods']
    return {
        'sales_count': sales['count'],
        'revenue': sales['revenue'],
        'cost_of_goods': sales['cost_of_goods'],
        'discounts': sales['discounts'],
        'gross_profit': gross_profit,
        'expenses': expenses_total,
        'net_profit': gross_profit - expenses_total,
    }


def daily_series(business, start, end):
    """One row per day (including days with no sales), for charts."""
    sales_by_day = {
        row['day']: row
        for row in sales_in_range(business, start, end)
        .annotate(day=TruncDate('sold_at'))
        .values('day')
        .annotate(revenue=_sum('total_amount'), cost=_sum('total_cost'))
    }
    expenses_by_day = {
        row['date']: row['total']
        for row in expenses_in_range(business, start, end).values('date').annotate(total=_sum('amount'))
    }
    rows = []
    day = start
    while day <= end:
        sales = sales_by_day.get(day, {'revenue': ZERO, 'cost': ZERO})
        rows.append({
            'date': day,
            'revenue': sales['revenue'],
            'gross_profit': sales['revenue'] - sales['cost'],
            'expenses': expenses_by_day.get(day, ZERO),
        })
        day += timedelta(days=1)
    return rows


def top_products(business, start, end, limit=10):
    item_profit = ExpressionWrapper(F('subtotal') - F('unit_cost') * F('quantity'), output_field=MONEY)
    return list(
        SaleItem.objects.filter(
            sale__business=business, sale__sold_at__date__gte=start, sale__sold_at__date__lte=end
        )
        .values('product_name')
        .annotate(quantity_sold=_sum('quantity'), revenue=_sum('subtotal'), profit=_sum(item_profit))
        .order_by('-revenue')[:limit]
    )


def payment_methods(business, start, end):
    labels = dict(PaymentMethod.choices)
    rows = (
        sales_in_range(business, start, end)
        .values('payment_method')
        .annotate(count=Count('id'), total=_sum('total_amount'))
        .order_by('-total')
    )
    return [{**row, 'label': labels.get(row['payment_method'], row['payment_method'])} for row in rows]


def expenses_by_category(business, start, end):
    labels = dict(Expense.Category.choices)
    rows = expenses_in_range(business, start, end).values('category').annotate(total=_sum('amount')).order_by('-total')
    return [{**row, 'label': labels.get(row['category'], row['category'])} for row in rows]


def stock_summary(business):
    products = Product.objects.filter(business=business, is_active=True)
    value = products.aggregate(
        cost_value=_sum(ExpressionWrapper(F('stock_quantity') * F('cost_price'), output_field=MONEY)),
        retail_value=_sum(ExpressionWrapper(F('stock_quantity') * F('selling_price'), output_field=MONEY)),
    )
    low = products.filter(stock_quantity__lte=F('low_stock_threshold')).order_by('stock_quantity')
    return {
        'product_count': products.count(),
        'stock_cost_value': value['cost_value'],
        'stock_retail_value': value['retail_value'],
        'low_stock_count': low.count(),
        'low_stock': list(low.values('id', 'name', 'stock_quantity', 'low_stock_threshold', 'unit')[:10]),
    }
