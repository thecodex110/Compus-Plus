from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# A donor can usually give whole blood again after about 3 months.
DONATION_GAP_DAYS = 90


class BloodGroup(models.TextChoices):
    A_POS = 'A+', _('A+')
    A_NEG = 'A-', _('A−')
    B_POS = 'B+', _('B+')
    B_NEG = 'B-', _('B−')
    AB_POS = 'AB+', _('AB+')
    AB_NEG = 'AB-', _('AB−')
    O_POS = 'O+', _('O+')
    O_NEG = 'O-', _('O−')


# Recipient group -> donor groups whose red cells they can receive.
COMPATIBLE_DONORS = {
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'A-': ['A-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    'AB-': ['A-', 'B-', 'AB-', 'O-'],
    'O+': ['O+', 'O-'],
    'O-': ['O-'],
}


class Donor(models.Model):
    """A student's entry in the blood directory. Opt-in: nothing is listed
    unless the student creates this and keeps `visible` on."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donor')
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices)
    visible = models.BooleanField(default=True, verbose_name=_('Show me in the directory'))
    last_donated = models.DateField(null=True, blank=True, verbose_name=_('Last donated (optional)'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__name']

    def __str__(self):
        return f'{self.user.name} ({self.blood_group})'

    @property
    def can_donate_from(self):
        if not self.last_donated:
            return None
        return self.last_donated + timedelta(days=DONATION_GAP_DAYS)

    @property
    def recently_donated(self):
        nxt = self.can_donate_from
        return bool(nxt and nxt > timezone.localdate())


class ContactReveal(models.Model):
    """Log of who looked up a donor's phone number. Used to rate-limit and to
    let a donor see who has their number."""

    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name='reveals')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-at']


class Hospital(models.Model):
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=250)
    phone = models.CharField(max_length=40, blank=True)
    emergency_phone = models.CharField(max_length=40, blank=True, verbose_name=_('Emergency / casualty phone'))
    distance_km = models.DecimalField(max_digits=4, decimal_places=1, verbose_name=_('Distance from COEP (km)'))
    has_blood_bank = models.BooleanField(default=False)
    is_24x7 = models.BooleanField(default=True, verbose_name=_('24×7 emergency'))
    maps_url = models.URLField(blank=True, verbose_name=_('Google Maps link'))
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['distance_km', 'name']

    def __str__(self):
        return self.name
