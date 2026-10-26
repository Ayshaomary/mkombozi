from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='report-dashboard'),
    path('summary/', views.SummaryReportView.as_view(), name='report-summary'),
]
