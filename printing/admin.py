from django.contrib import admin

from .models import OrderEvent, OrderLine, PrintOrder, Shop, StationeryItem


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'location', 'is_open']
    list_filter = ['is_open']
    search_fields = ['name', 'owner__email']
    raw_id_fields = ['owner']


@admin.register(StationeryItem)
class StationeryItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop', 'price', 'in_stock']
    list_filter = ['shop', 'in_stock']


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    readonly_fields = ['name', 'unit_price', 'quantity']


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ['status', 'by', 'note', 'at']
    can_delete = False


@admin.register(PrintOrder)
class PrintOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'shop', 'student', 'status', 'price', 'delivery_point', 'created_at']
    list_filter = ['status', 'shop', 'delivery_point']
    search_fields = ['student__email', 'student__name', 'txn_last_digits']
    # Files are private; admins see metadata, not the documents themselves.
    exclude = ['file', 'payment_screenshot']
    readonly_fields = ['price', 'price_breakdown', 'placed_at', 'file_deleted_at']
    inlines = [OrderLineInline, OrderEventInline]
