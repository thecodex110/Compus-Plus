from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'title', 'place', 'date', 'user', 'status', 'created_at']
    list_filter = ['type', 'status']
    search_fields = ['title', 'description', 'place', 'user__email']
