from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

from .models import Business, PasswordResetCode, User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ('phone', 'first_name', 'business', 'role')


class UserChangeForm(BaseUserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'location', 'created_at']
    search_fields = ['name', 'phone']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ['phone']
    list_display = ['phone', 'first_name', 'last_name', 'business', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['phone', 'first_name', 'last_name', 'business__name']
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Business', {'fields': ('business', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'business', 'role', 'password1', 'password2'),
        }),
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
