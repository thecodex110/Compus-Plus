from django import forms

from .models import Location, ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    category = forms.ChoiceField(choices=ServiceRequest.Category.choices, widget=forms.RadioSelect,
                                 error_messages={'required': 'Pick what you need.'})
    location = forms.ModelChoiceField(queryset=Location.objects.all(), widget=forms.HiddenInput,
                                      error_messages={'required': 'Pick the building, floor and classroom.'})

    class Meta:
        model = ServiceRequest
        fields = ['category', 'location', 'note']
        widgets = {
            'note': forms.TextInput(attrs={'placeholder': 'Optional — e.g. "bring the projector remote"'}),
        }
