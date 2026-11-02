import math
import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

@deconstructible
class PrivateStorage(FileSystemStorage):
    """Print files and payment screenshots: never served from /media, only through
    views that check who is asking. The folder is read from settings on each use,
    so it isn't frozen into migrations and test overrides apply."""

    def __init__(self):
        super().__init__()

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


private_storage = PrivateStorage()


def _path(folder, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'{folder}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}'


def qr_path(instance, filename):
    return _path('shop_qr', filename)


def print_file_path(instance, filename):
    return _path('print_files', filename)


def screenshot_path(instance, filename):
    return _path('payment_screenshots', filename)


def money(**kw):
    return models.DecimalField(max_digits=7, decimal_places=2, **kw)


class Shop(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop')
    name = models.CharField(max_length=80)
    location = models.CharField(max_length=120, blank=True, help_text=_('e.g. Opposite main gate, Shivajinagar'))
    phone = models.CharField(max_length=15, blank=True)
    qr_image = models.ImageField(upload_to=qr_path, blank=True, verbose_name=_('Payment QR code'))
    upi_id = models.CharField(max_length=60, blank=True, verbose_name=_('UPI ID (optional)'))
    is_open = models.BooleanField(default=False)

    # Price list, in rupees.
    bw_single = money(default=Decimal('1.00'), verbose_name=_('B/W single side, per page'))
    bw_double = money(default=Decimal('0.80'), verbose_name=_('B/W double side, per page'))
    color_single = money(default=Decimal('5.00'), verbose_name=_('Colour single side, per page'))
    color_double = money(default=Decimal('4.50'), verbose_name=_('Colour double side, per page'))
    a3_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('2.00'),
                                        verbose_name=_('A3 costs this many times A4'))
    staple_price = money(default=Decimal('0.00'), verbose_name=_('Staple, per copy'))
    spiral_price = money(default=Decimal('25.00'), verbose_name=_('Spiral binding, per copy'))
    hard_binding_price = money(default=Decimal('80.00'), verbose_name=_('Hard binding, per copy'))
    delivery_charge = money(default=Decimal('0.00'), verbose_name=_('Delivery charge, per order'))

    class Meta:
        ordering = ['-is_open', 'name']

    def __str__(self):
        return self.name

    @property
    def accepts_orders(self):
        return self.is_open and bool(self.qr_image)

    def per_page(self, color, sides):
        return {
            ('bw', 'single'): self.bw_single, ('bw', 'double'): self.bw_double,
            ('color', 'single'): self.color_single, ('color', 'double'): self.color_double,
        }[(color, sides)]

    def binding_price(self, binding):
        return {'none': Decimal('0'), 'staple': self.staple_price, 'spiral': self.spiral_price,
                'hard': self.hard_binding_price}[binding]

    def quote(self, pages, color, sides, paper_size, binding, copies):
        """Return (total_rupees, breakdown_dict). Total is rounded up to a whole rupee."""
        rate = self.per_page(color, sides)
        if paper_size == 'A3':
            rate *= self.a3_multiplier
        printing = rate * pages
        bind = self.binding_price(binding)
        per_copy = printing + bind
        subtotal = per_copy * copies
        total = Decimal(math.ceil(subtotal + self.delivery_charge))
        return total, {
            'pages': pages, 'rate': str(rate.quantize(Decimal('0.01'))), 'printing': str(printing.quantize(Decimal('0.01'))),
            'binding': str(bind), 'per_copy': str(per_copy.quantize(Decimal('0.01'))), 'copies': copies,
            'subtotal': str(subtotal.quantize(Decimal('0.01'))), 'delivery': str(self.delivery_charge),
        }


class StationeryItem(models.Model):
    """Something a shop sells besides printing: pens, notebooks, files, lab journals…"""

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='stationery')
    name = models.CharField(max_length=80)
    price = money()
    in_stock = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} (₹{self.price})'


class PrintOrder(models.Model):
    class Color(models.TextChoices):
        BW = 'bw', _('Black & white')
        COLOR = 'color', _('Colour')

    class Sides(models.TextChoices):
        SINGLE = 'single', _('Single sided')
        DOUBLE = 'double', _('Double sided')

    class PaperSize(models.TextChoices):
        A4 = 'A4', 'A4'
        A3 = 'A3', 'A3'

    class Binding(models.TextChoices):
        NONE = 'none', _('None')
        STAPLE = 'staple', _('Staple')
        SPIRAL = 'spiral', _('Spiral')
        HARD = 'hard', _('Hard binding')

    class DeliveryPoint(models.TextChoices):
        MAIN_GATE = 'main_gate', _('Main Gate')
        LIBRARY = 'library', _('Library')

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Awaiting payment')
        PLACED = 'placed', _('Placed')
        VERIFIED = 'verified', _('Payment Verified')
        PRINTING = 'printing', _('Printing')
        OUT = 'out', _('Out for Delivery')
        DELIVERED = 'delivered', _('Delivered')
        REJECTED = 'rejected', _('Rejected')

    # The shop moves an order along this chain.
    NEXT_STATUS = {
        Status.PLACED: Status.VERIFIED,
        Status.VERIFIED: Status.PRINTING,
        Status.PRINTING: Status.OUT,
        Status.OUT: Status.DELIVERED,
    }
    ACTIVE = (Status.PLACED, Status.VERIFIED, Status.PRINTING, Status.OUT)
    TRACKED = (Status.PLACED, Status.VERIFIED, Status.PRINTING, Status.OUT, Status.DELIVERED)

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='print_orders')
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='orders')
    file = models.FileField(upload_to=print_file_path, storage=private_storage, blank=True)
    file_name = models.CharField(max_length=200, blank=True)
    # Zero for a stationery-only order.
    page_count = models.PositiveIntegerField(default=0)

    color = models.CharField(max_length=5, choices=Color.choices, default=Color.BW)
    sides = models.CharField(max_length=6, choices=Sides.choices, default=Sides.SINGLE)
    copies = models.PositiveSmallIntegerField(default=1)
    paper_size = models.CharField(max_length=2, choices=PaperSize.choices, default=PaperSize.A4)
    binding = models.CharField(max_length=6, choices=Binding.choices, default=Binding.NONE)
    page_range = models.CharField(max_length=60, blank=True, help_text=_('e.g. 1-5, 8, 10-12. Empty = all pages'))
    pages_to_print = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=200, blank=True)

    price = models.DecimalField(max_digits=8, decimal_places=2)
    price_breakdown = models.JSONField(default=dict)

    payment_screenshot = models.ImageField(upload_to=screenshot_path, storage=private_storage, blank=True)
    txn_last_digits = models.CharField(max_length=6, blank=True)
    delivery_point = models.CharField(max_length=10, choices=DeliveryPoint.choices, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    reject_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    placed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['shop', 'status'])]

    def __str__(self):
        return f'Order #{self.pk} · {self.shop}'

    @property
    def next_status(self):
        return self.NEXT_STATUS.get(self.status)

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    @property
    def has_print(self):
        return self.pages_to_print > 0

    def recalc(self, lines=None):
        """Price = printing (if any) + stationery + delivery, rounded up to a whole rupee."""
        lines = list(self.lines.all()) if lines is None else lines
        breakdown, printing = {}, Decimal('0')
        if self.has_print:
            _, breakdown = self.shop.quote(
                self.pages_to_print, self.color, self.sides, self.paper_size, self.binding, self.copies)
            printing = Decimal(breakdown['subtotal'])
        stationery = sum((line.total for line in lines), Decimal('0'))
        self.price = Decimal(math.ceil(printing + stationery + self.shop.delivery_charge))
        breakdown.update({'stationery': str(stationery.quantize(Decimal('0.01'))),
                          'delivery': str(self.shop.delivery_charge)})
        self.price_breakdown = breakdown

    @property
    def summary(self):
        """One line for lists: '12 pg × 2 · B/W' and/or '3 stationery items'."""
        parts = []
        if self.has_print:
            parts.append(_('%(pages)s pg × %(copies)s · %(color)s') % {
                'pages': self.pages_to_print, 'copies': self.copies, 'color': self.get_color_display()})
        n = sum(line.quantity for line in self.lines.all())
        if n:
            parts.append(ngettext('%(n)s stationery item', '%(n)s stationery items', n) % {'n': n})
        return ' + '.join(parts)

    def log(self, status, by, note=''):
        OrderEvent.objects.create(order=self, status=status, by=by, note=note)

    def delete_print_file(self):
        if self.file:
            self.file.delete(save=False)
        self.file_deleted_at = timezone.now()
        self.save(update_fields=['file', 'file_deleted_at', 'updated_at'])


class OrderEvent(models.Model):
    order = models.ForeignKey(PrintOrder, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=10, choices=PrintOrder.Status.choices)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.CharField(max_length=200, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['at']


class OrderLine(models.Model):
    """A stationery item in an order. Name and price are copied so later price
    changes or deletions don't alter a placed order."""

    order = models.ForeignKey(PrintOrder, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(StationeryItem, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=80)
    unit_price = money()
    quantity = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['name']

    @property
    def total(self):
        return self.unit_price * self.quantity
