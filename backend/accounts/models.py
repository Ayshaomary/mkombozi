import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from .utils import normalize_phone


class Business(models.Model):
    """A shop or small business. All products, sales and expenses belong to one business."""

    class Type(models.TextChoices):
        # The app suggests product categories that fit the type (see categorySuggestions in translations.js)
        SUPERMARKET = 'supermarket', 'Supermarket / general shop'
        FOOD = 'food', 'Food and drinks'
        COSMETICS = 'cosmetics', 'Cosmetics and beauty'
        CLOTHING = 'clothing', 'Clothes and shoes'
        ACCESSORIES = 'accessories', 'Accessories'
        HARDWARE = 'hardware', 'Hardware and building'
        ELECTRONICS = 'electronics', 'Electronics and phones'
        PHARMACY = 'pharmacy', 'Pharmacy'
        STATIONERY = 'stationery', 'Stationery and books'
        AGROVET = 'agrovet', 'Agrovet (farming and animals)'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=150)
    business_type = models.CharField(max_length=20, choices=Type.choices, default=Type.OTHER)
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
    # Points to the user's current profile photo (see Avatar); a new photo gets a new key
    avatar_key = models.UUIDField(null=True, blank=True, editable=False)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['first_name']

    objects = UserManager()

    def __str__(self):
        return f'{self.get_full_name() or self.phone} ({self.phone})'

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER


class PasswordResetCode(models.Model):
    """A one-time code sent by SMS, so a user who forgot their password can choose a new one."""

    LIFETIME = timedelta(minutes=10)
    MAX_ATTEMPTS = 5

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_codes')
    # Only a hash is stored, like a password, so the code can't be read from the database
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Reset code for {self.user} at {self.created_at:%Y-%m-%d %H:%M}'


class Avatar(models.Model):
    """A user's profile photo, kept in the database.

    The app shrinks photos to a small square before uploading, so they are only a few KB. Kept in
    the database rather than as files because Render's free servers delete files on every restart.
    The key is part of the photo's address and changes with every new photo, so browsers can keep a
    photo forever without ever showing an old one.
    """

    key = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='avatar')
    image = models.BinaryField()
    content_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Photo of {self.user}'
