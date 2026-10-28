from django.conf import settings
from django.db import models
from django.utils import timezone


def floor_key(floor):
    """Sort floors the way people expect: basement, ground, then 1, 2, 3…"""
    f = floor.strip().upper()
    if f in ('B', 'LG', 'BASEMENT'):
        return (-2, f)
    if f in ('G', 'GF', 'GROUND', '0'):
        return (-1, f)
    return (int(f), f) if f.isdigit() else (99, f)


class Location(models.Model):
    building = models.CharField(max_length=80)
    floor = models.CharField(max_length=20)
    classroom = models.CharField(max_length=40)

    class Meta:
        ordering = ['building', 'floor', 'classroom']
        constraints = [
            models.UniqueConstraint(fields=['building', 'floor', 'classroom'], name='unique_location'),
        ]

    def __str__(self):
        return f'{self.building} · Floor {self.floor} · {self.classroom}'


class ServiceRequest(models.Model):
    class Category(models.TextChoices):
        MEDICAL = 'medical', 'Medical'
        SECURITY = 'security', 'Security'
        CLEANING = 'cleaning', 'Cleaning'
        ITEM = 'item', 'Item Request'
        OTHER = 'other', 'Other'

    class Priority(models.IntegerChoices):
        # Lower value sorts first.
        HIGH = 0, 'High'
        NORMAL = 1, 'Normal'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'

    HIGH_PRIORITY_CATEGORIES = (Category.MEDICAL, Category.SECURITY)
    # Status → the only status it may move to next.
    NEXT_STATUS = {
        Status.PENDING: Status.ACCEPTED,
        Status.ACCEPTED: Status.IN_PROGRESS,
        Status.IN_PROGRESS: Status.DONE,
    }
    OPEN_STATUSES = (Status.PENDING, Status.ACCEPTED, Status.IN_PROGRESS)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='service_requests')
    category = models.CharField(max_length=10, choices=Category.choices)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='requests')
    note = models.CharField(max_length=300, blank=True)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    assigned_staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='assigned_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', '-created_at']
        indexes = [models.Index(fields=['status', 'priority', 'created_at'])]

    def __str__(self):
        return f'#{self.pk} {self.get_category_display()} @ {self.location}'

    def save(self, *args, **kwargs):
        self.priority = (self.Priority.HIGH if self.category in self.HIGH_PRIORITY_CATEGORIES
                         else self.Priority.NORMAL)
        super().save(*args, **kwargs)

    @property
    def is_high(self):
        return self.priority == self.Priority.HIGH

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def next_status(self):
        return self.NEXT_STATUS.get(self.status)

    def advance(self, staff):
        """Move to the next status on behalf of `staff`. Returns False if not allowed."""
        nxt = self.next_status
        if nxt is None:
            return False
        if self.status == self.Status.PENDING:
            self.assigned_staff = staff
        elif self.assigned_staff_id != staff.pk:
            return False
        now = timezone.now()
        stamp = {self.Status.ACCEPTED: 'accepted_at', self.Status.IN_PROGRESS: 'started_at',
                 self.Status.DONE: 'done_at'}[nxt]
        setattr(self, stamp, now)
        self.status = nxt
        self.save()
        RequestEvent.objects.create(request=self, status=nxt, by=staff)
        return True


class RequestEvent(models.Model):
    """Every status change, so the full history of a request is kept."""

    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=12, choices=ServiceRequest.Status.choices)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['at']
