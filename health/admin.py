from django.contrib import admin

from .models import ContactReveal, Donor, Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ['name', 'distance_km', 'phone', 'emergency_phone', 'has_blood_bank', 'is_24x7']
    list_editable = ['distance_km', 'phone', 'emergency_phone', 'has_blood_bank', 'is_24x7']
    search_fields = ['name', 'address']


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ['user', 'blood_group', 'visible', 'last_donated', 'updated_at']
    list_filter = ['blood_group', 'visible']
    search_fields = ['user__name', 'user__email']


@admin.register(ContactReveal)
class ContactRevealAdmin(admin.ModelAdmin):
    list_display = ['viewer', 'donor', 'at']
    readonly_fields = ['viewer', 'donor', 'at']
