from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Location, ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    category = forms.ChoiceField(choices=ServiceRequest.Category.choices, widget=forms.RadioSelect,
                                 error_messages={'required': _('Pick what you need.')})
    location = forms.ModelChoiceField(queryset=Location.objects.all(), widget=forms.HiddenInput,
                                      error_messages={'required': _('Pick the building, floor and classroom.')})

    class Meta:
        model = ServiceRequest
        fields = ['category', 'location', 'note']
        widgets = {
            'note': forms.TextInput(attrs={'placeholder': _('Optional — e.g. "bring the projector remote"')}),
        }
