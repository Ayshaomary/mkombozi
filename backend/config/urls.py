"""SAVIOR URL configuration. All API endpoints start with /api/."""

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from config.views import PublicAPIRootView, home
from expenses.views import ExpenseViewSet, RecurringExpenseViewSet
from inventory.views import CategoryViewSet, ProductViewSet, StockMovementViewSet
from notifications.views import NotificationViewSet
from production.views import ProductionRunViewSet, RecipeViewSet
from sales.views import SaleViewSet

router = DefaultRouter()
router.APIRootView = PublicAPIRootView
router.register('categories', CategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')
router.register('stock-movements', StockMovementViewSet, basename='stock-movement')
router.register('sales', SaleViewSet, basename='sale')
router.register('expenses', ExpenseViewSet, basename='expense')
router.register('recurring-expenses', RecurringExpenseViewSet, basename='recurring-expense')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('recipes', RecipeViewSet, basename='recipe')
router.register('production', ProductionRunViewSet, basename='production-run')

admin.site.site_header = 'SAVIOR Inventory System - Admin'
admin.site.site_title = 'SAVIOR Inventory System'

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/subscription/', include('subscriptions.urls')),
    path('api/admin/', include('adminpanel.urls')),
    path('api/', include(router.urls)),
]
