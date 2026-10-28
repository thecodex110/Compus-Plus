from django.contrib import admin

from .models import Location, RequestEvent, ServiceRequest


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['building', 'floor', 'classroom']
    list_filter = ['building']
    search_fields = ['building', 'classroom']


class RequestEventInline(admin.TabularInline):
    model = RequestEvent
    extra = 0
    readonly_fields = ['status', 'by', 'at']
    can_delete = False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'category', 'priority', 'status', 'location', 'user', 'assigned_staff', 'created_at']
    list_filter = ['status', 'category', 'priority']
    search_fields = ['note', 'user__email', 'user__name']
    readonly_fields = ['priority', 'created_at', 'accepted_at', 'started_at', 'done_at', 'updated_at']
    inlines = [RequestEventInline]
