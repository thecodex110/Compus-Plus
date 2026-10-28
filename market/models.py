import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

MAX_PHOTOS = 5


def photo_path(instance, filename):
    return f'market/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg'


class Listing(models.Model):
    class Category(models.TextChoices):
        BOOKS = 'books', 'Books & Notes'
        ELECTRONICS = 'electronics', 'Electronics'
        INSTRUMENTS = 'instruments', 'Calculators & Instruments'
        LAB = 'lab', 'Lab & Drawing gear'
        CYCLES = 'cycles', 'Cycles'
        HOSTEL = 'hostel', 'Hostel & Room'
        CLOTHING = 'clothing', 'Clothing'
        OTHER = 'other', 'Other'

    class Condition(models.TextChoices):
        NEW = 'new', 'New'
        LIKE_NEW = 'like_new', 'Like new'
        GOOD = 'good', 'Good'
        FAIR = 'fair', 'Fair'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        SOLD = 'sold', 'Sold'
        REMOVED = 'removed', 'Removed by admin'

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listings')
    title = models.CharField(max_length=80)
    price = models.PositiveIntegerField(help_text='In rupees. 0 = free')
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
