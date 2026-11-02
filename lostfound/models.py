import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def photo_path(instance, filename):
    return f'lostfound/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg'


class Post(models.Model):
    class Type(models.TextChoices):
        LOST = 'lost', _('Lost')
        FOUND = 'found', _('Found')

    class Status(models.TextChoices):
        OPEN = 'open', _('Open')
        RETURNED = 'returned', _('Returned')
        REMOVED = 'removed', _('Removed by admin')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lostfound_posts')
    type = models.CharField(max_length=5, choices=Type.choices)
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=600, blank=True)
    photo = models.ImageField(upload_to=photo_path, blank=True)
    place = models.CharField(max_length=80, help_text=_('Where it was lost or found'))
    date = models.DateField(default=timezone.localdate, help_text=_('When it was lost or found'))
    # Phone is personal data, so it is shown only if the uploader ticks this.
    show_phone = models.BooleanField(default=False)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Newest uploads first, then by the date of the loss/find.
        ordering = ['-created_at', '-date']
        indexes = [models.Index(fields=['status', '-created_at'])]

    def __str__(self):
        return f'{self.get_type_display()}: {self.title}'
