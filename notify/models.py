from django.conf import settings
from django.db import models
from django.utils import translation


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=250, blank=True)
    url = models.CharField(max_length=200, blank=True)
    urgent = models.BooleanField(default=False)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'read', '-created_at'])]

    def __str__(self):
        return f'{self.user}: {self.title}'


def notify(users, title, body='', url='', urgent=False):
    """Create one notification per user, written in that user's language.

    `title` and `body` may be strings or zero-argument callables; callables are
    evaluated once per recipient with their language active, so a Hindi user
    gets Hindi text even when an English user triggered it.
    """
    if hasattr(users, 'pk'):
        users = [users]
    items = []
    for u in users:
        with translation.override(getattr(u, 'ui_language', None) or settings.LANGUAGE_CODE):
            t = str(title() if callable(title) else title)
            b = str(body() if callable(body) else body)
        items.append(Notification(user=u, title=t[:120], body=b[:250], url=url, urgent=urgent))
    Notification.objects.bulk_create(items)
