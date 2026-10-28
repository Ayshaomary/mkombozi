from django.urls import path

from . import views

urlpatterns = [
    path('overview/', views.OverviewView.as_view(), name='admin-overview'),
    path('activities/', views.ActivityListView.as_view(), name='admin-activities'),
    path('users/', views.UserListView.as_view(), name='admin-users'),
    path('users/<int:pk>/', views.UserUpdateView.as_view(), name='admin-user-update'),
    path('businesses/', views.BusinessListView.as_view(), name='admin-businesses'),
]
