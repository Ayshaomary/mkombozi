from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

from .models import Business, PasswordResetCode, User
from .utils import normalize_phone, phone_too_long


class PhoneFormMixin:
    """Save phone numbers in the same +255 format the login uses, so admin-made users can log in."""

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if phone_too_long(phone):
            raise forms.ValidationError('Phone number is too long. Use 10 digits, e.g. 0712 345 678.')
        return normalize_phone(phone)


def activity_link(field, obj):
    url = reverse('admin:activity_activitylog_changelist') + f'?{field}={obj.pk}'
    return format_html('<a href="{}">View activity</a>', url)


class UserCreationForm(PhoneFormMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ('phone', 'first_name', 'business', 'role', 'is_staff', 'is_superuser')


class UserChangeForm(PhoneFormMixin, BaseUserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'location', 'created_at', 'activity']
    search_fields = ['name', 'phone']

    @admin.display(description='Activity')
    def activity(self, obj):
        return activity_link('business__id__exact', obj)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ['phone']
    list_display = ['phone', 'first_name', 'last_name', 'business', 'role', 'is_active', 'activity']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['phone', 'first_name', 'last_name', 'business__name']
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Business', {'fields': ('business', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    @admin.display(description='Activity')
    def activity(self, obj):
        return activity_link('user__id__exact', obj)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'business', 'role', 'password1', 'password2'),
        }),
        # Tick both to make an admin who can log in to this page. Leave "Business" empty for an admin.
        ('Admin access', {'fields': ('is_staff', 'is_superuser')}),
    )


@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    """Read-only: shows whether a user asked for a reset code and used it. The code itself is never shown."""

    list_display = ['user', 'created_at', 'attempts', 'used_at']
    search_fields = ['user__phone', 'user__first_name']
    exclude = ['code_hash']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
