from django.contrib import admin

from .models import Listing, ListingPhoto


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'price', 'category', 'condition', 'seller', 'status', 'created_at']
    list_filter = ['status', 'category', 'condition']
    search_fields = ['title', 'description', 'seller__email']
    inlines = [ListingPhotoInline]
