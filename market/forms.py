from django import forms

from lostfound.forms import MAX_UPLOAD_MB, compress_image

from .models import MAX_PHOTOS, Listing, ListingPhoto


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        out = []
        for f in files:
            f = super().clean(f, initial)
            if f.size > MAX_UPLOAD_MB * 1024 * 1024:
                raise forms.ValidationError(f'Each photo must be under {MAX_UPLOAD_MB} MB.')
            out.append(compress_image(f))
        return out


class ListingForm(forms.ModelForm):
    new_photos = MultipleImageField(required=False, label='Photos',
                                    widget=MultipleFileInput(attrs={'accept': 'image/*', 'multiple': True}))
    remove_photos = forms.ModelMultipleChoiceField(queryset=None, required=False,
                                                   widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Listing
        fields = ['title', 'price', 'category', 'condition', 'description', 'show_phone']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Engineering Graphics drafter'}),
            'price': forms.NumberInput(attrs={'min': 0, 'inputmode': 'numeric', 'placeholder': '₹'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'How old, any defects, edition, where to meet…'}),
        }
        labels = {'price': 'Price (₹)', 'show_phone': 'Show my phone number to buyers'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing = self.instance.photos.all() if self.instance.pk else ListingPhoto.objects.none()
        self.fields['remove_photos'].queryset = self.existing
        for name in ('category', 'condition'):
            self.fields[name].choices = [c for c in self.fields[name].choices if c[0]]
            self.fields[name].choices = [('', 'Choose…')] + self.fields[name].choices

    def clean_price(self):
        price = self.cleaned_data['price']
        if price > 500000:
            raise forms.ValidationError('That price looks too high.')
        return price

    def clean(self):
        data = super().clean()
        kept = len(self.existing) - len(data.get('remove_photos') or [])
        total = kept + len(data.get('new_photos') or [])
        if total == 0:
            self.add_error('new_photos', 'Add at least one photo.')
        elif total > MAX_PHOTOS:
            self.add_error('new_photos', f'At most {MAX_PHOTOS} photos per listing.')
        return data

    def save(self, commit=True):
        listing = super().save(commit=commit)
        for photo in self.cleaned_data.get('remove_photos') or []:
            photo.delete()
        start = (self.existing.order_by('-position').values_list('position', flat=True).first() or 0) + 1
        for i, f in enumerate(self.cleaned_data.get('new_photos') or []):
            listing.photos.create(image=f, position=start + i)
        return listing
