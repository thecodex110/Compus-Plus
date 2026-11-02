import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

MAX_PHOTOS = 5


def photo_path(instance, filename):
    return f'market/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg'


class Listing(models.Model):
    class Category(models.TextChoices):
        BOOKS = 'books', _('Books & Notes')
        ELECTRONICS = 'electronics', _('Electronics')
        INSTRUMENTS = 'instruments', _('Calculators & Instruments')
        LAB = 'lab', _('Lab & Drawing gear')
        CYCLES = 'cycles', _('Cycles')
        HOSTEL = 'hostel', _('Hostel & Room')
        CLOTHING = 'clothing', _('Clothing')
        OTHER = 'other', _('Other')

    class Condition(models.TextChoices):
        NEW = 'new', _('New')
        LIKE_NEW = 'like_new', _('Like new')
        GOOD = 'good', _('Good')
        FAIR = 'fair', _('Fair')

    class Status(models.TextChoices):
        AVAILABLE = 'available', _('Available')
        SOLD = 'sold', _('Sold')
        REMOVED = 'removed', _('Removed by admin')

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listings')
    title = models.CharField(max_length=80)
    price = models.PositiveIntegerField(help_text=_('In rupees. 0 = free'))
    category = models.CharField(max_length=12, choices=Category.choices)
    condition = models.CharField(max_length=9, choices=Condition.choices)
    description = models.TextField(max_length=1000, blank=True)
    # Phone is personal data, so it is shown only if the seller ticks this.
    show_phone = models.BooleanField(default=False)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'category', '-created_at'])]

    def __str__(self):
        return f'{self.title} (₹{self.price})'

    @property
    def cover(self):
        photos = list(self.photos.all())
        return photos[0] if photos else None


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to=photo_path)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']

    def delete(self, *args, **kwargs):
        self.image.delete(save=False)
        super().delete(*args, **kwargs)
