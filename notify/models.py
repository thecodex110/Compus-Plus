from django.conf import settings
from django.db import models


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
    """Create one notification per user. `users` may be a user or an iterable."""
    if hasattr(users, 'pk'):
        users = [users]
    Notification.objects.bulk_create(
        [Notification(user=u, title=title[:120], body=body[:250], url=url, urgent=urgent) for u in users])
