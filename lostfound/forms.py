from io import BytesIO

from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Post

MAX_UPLOAD_MB = 8
MAX_SIDE = 1280


def compress_image(upload):
    """Shrink to MAX_SIDE, fix rotation, drop EXIF (location etc.) and save as JPEG."""
    try:
        img = Image.open(upload)
        img = ImageOps.exif_transpose(img).convert('RGB')
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError('That file is not a valid image.')
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = BytesIO()
    img.save(buf, 'JPEG', quality=82, optimize=True)
    return InMemoryUploadedFile(buf, 'photo', 'photo.jpg', 'image/jpeg', buf.tell(), None)


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['type', 'photo', 'title', 'description', 'place', 'date', 'show_phone']
        widgets = {
            'type': forms.RadioSelect,
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Black HP laptop charger'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Colour, brand, stickers, anything that helps identify it'}),
            'place': forms.TextInput(attrs={'placeholder': 'e.g. Library reading hall'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {'show_phone': 'Show my phone number on this post'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type'].choices = Post.Type.choices
        self.fields['date'].widget.attrs['max'] = timezone.localdate().isoformat()

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo or not hasattr(photo, 'content_type'):
            return photo
        if photo.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f'Photo must be under {MAX_UPLOAD_MB} MB.')
        return compress_image(photo)

    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError('Date cannot be in the future.')
        return date

    def clean(self):
        data = super().clean()
        if data.get('type') == Post.Type.FOUND and not data.get('photo'):
            self.add_error('photo', 'Add a photo so the owner can recognise their item.')
        return data
