from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ['email', 'name', 'role', 'department', 'year', 'is_active']
    list_filter = ['role', 'is_active', 'department']
    search_fields = ['email', 'name', 'phone']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('name', 'phone', 'role', 'department', 'year')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',),
                'fields': ('email', 'name', 'phone', 'role', 'department', 'password1', 'password2')}),
    )
