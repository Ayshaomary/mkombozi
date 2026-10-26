from django.contrib.auth.backends import ModelBackend

from .utils import normalize_phone


class PhoneBackend(ModelBackend):
    """Log in with a phone number in any format (0712..., 255712..., +255712...).

    Used by every login: the app's API and the Django admin.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        phone = username or kwargs.get('phone')
        return super().authenticate(request, username=normalize_phone(phone), password=password)
