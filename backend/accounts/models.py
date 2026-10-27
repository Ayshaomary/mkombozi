from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from .utils import normalize_phone


class Business(models.Model):
    """A shop or small business. All products, sales and expenses belong to one business."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # When the automatic tasks (recurring expenses, alerts) last ran for this business
    automations_ran_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name_plural = 'businesses'

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Creates users who log in with a phone number instead of a username."""

    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        # Same format everywhere, so '0712...' typed in createsuperuser matches '+255712...' at login
        user = self.model(phone=normalize_phone(phone), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        STAFF = 'staff', 'Staff'

    username = None
    phone = models.CharField(max_length=20, unique=True)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='users', null=True, blank=True
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OWNER)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['first_name']

    objects = UserManager()

    def __str__(self):
        return f'{self.get_full_name() or self.phone} ({self.phone})'

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER
