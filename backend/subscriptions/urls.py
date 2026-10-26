from django.urls import path

from . import views

urlpatterns = [
    path('', views.CurrentSubscriptionView.as_view(), name='subscription-current'),
    path('plans/', views.PlanListView.as_view(), name='subscription-plans'),
    path('payments/', views.SubscriptionPaymentListCreateView.as_view(), name='subscription-payments'),
]
