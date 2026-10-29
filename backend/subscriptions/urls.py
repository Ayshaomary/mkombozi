from django.urls import path

from . import views

urlpatterns = [
    path('', views.CurrentSubscriptionView.as_view(), name='subscription-current'),
    path('plans/', views.PlanListView.as_view(), name='subscription-plans'),
    path('payments/', views.SubscriptionPaymentListCreateView.as_view(), name='subscription-payments'),
    path('payments/<int:pk>/', views.SubscriptionPaymentDetailView.as_view(), name='subscription-payment-detail'),
    path('sonicpesa/webhook/', views.SonicPesaWebhookView.as_view(), name='sonicpesa-webhook'),
    path('clickpesa/webhook/', views.ClickPesaWebhookView.as_view(), name='clickpesa-webhook'),
]
