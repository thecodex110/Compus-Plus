from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import BloodGroup, Donor


class DonorForm(forms.ModelForm):
    consent = forms.BooleanField(
        label=_('I agree that logged-in COEP students and teachers can see my name, department, '
                'year, blood group and phone number in the blood directory.'))

    class Meta:
        model = Donor
        fields = ['blood_group', 'last_donated', 'visible']
        widgets = {
            'blood_group': forms.RadioSelect,
            'last_donated': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['blood_group'].choices = BloodGroup.choices
        self.fields['last_donated'].widget.attrs['max'] = timezone.localdate().isoformat()
        if self.instance.pk:
            # Consent was given when the entry was created.
            self.fields['consent'].required = False
            self.fields['consent'].initial = True

    def clean_last_donated(self):
        d = self.cleaned_data.get('last_donated')
        if d and d > timezone.localdate():
            raise forms.ValidationError(_('Date cannot be in the future.'))
        return d
