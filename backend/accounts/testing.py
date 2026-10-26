"""Helpers shared by the tests of all apps."""

from rest_framework.test import APIClient

from subscriptions.models import Subscription

from .models import Business, User


def make_business(name='Duka la Juma', phone='+255712000001', role=User.Role.OWNER):
    business = Business.objects.create(name=name)
    Subscription.start_trial(business)
    user = User.objects.create_user(phone=phone, password='siri-kali-123', first_name='Juma', business=business, role=role)
    return business, user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client
