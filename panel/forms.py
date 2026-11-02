import re

from django import forms
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from health.models import Hospital
from printing.models import Shop
from services.models import Location


class CreateUserForm(forms.ModelForm):
    """Admins create BVG staff, shops and other admins (and can add students/teachers)."""

    password1 = forms.CharField(label=_('Password'), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_('Confirm password'), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['name', 'email', 'phone', 'role', 'department', 'year']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_('An account with this email already exists.'))
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone and not re.fullmatch(r'[6-9]\d{9}', phone):
            raise forms.ValidationError(_('Enter a 10-digit mobile number.'))
        return phone

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', _('Passwords do not match.'))
        if p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_staff = user.role == User.Role.ADMIN  # lets admins open /django-admin/ too
        if commit:
            user.save()
        return user


class BulkLocationForm(forms.Form):
    building = forms.CharField(max_length=80)
    floor = forms.CharField(max_length=20, help_text=_('e.g. G, 1, 2'))
    classrooms = forms.CharField(max_length=500, help_text=_('Comma-separated, e.g. 101, 102, Seminar Hall'))

    def rooms(self):
        return [r.strip()[:40] for r in self.cleaned_data['classrooms'].split(',') if r.strip()]

    def save(self):
        added = 0
        for room in self.rooms():
            _, created = Location.objects.get_or_create(
                building=self.cleaned_data['building'].strip(), floor=self.cleaned_data['floor'].strip(),
                classroom=room)
            added += created
        return added


class HospitalForm(forms.ModelForm):
    class Meta:
        model = Hospital
        fields = ['name', 'address', 'distance_km', 'phone', 'emergency_phone', 'has_blood_bank', 'is_24x7',
                  'maps_url', 'notes']


class ShopAdminForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'location', 'phone', 'is_open']
        labels = {'is_open': _('Open for orders')}

    def clean_is_open(self):
        is_open = self.cleaned_data['is_open']
        if is_open and not self.instance.qr_image:
            raise forms.ValidationError(_("This shop hasn't uploaded a payment QR code yet."))
        return is_open
