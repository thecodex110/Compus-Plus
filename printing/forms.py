import re

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from lostfound.forms import compress_image

from .models import OrderLine, PrintOrder, Shop, StationeryItem

IMAGE_TYPES = ('jpg', 'jpeg', 'png')
ALLOWED_TYPES = ('pdf',) + IMAGE_TYPES


def count_pages(upload):
    """Pages in an uploaded PDF or image (an image is one page)."""
    ext = upload.name.rsplit('.', 1)[-1].lower() if '.' in upload.name else ''
    if ext not in ALLOWED_TYPES:
        raise forms.ValidationError(_('Upload a PDF or an image (JPG/PNG). Convert Word/PPT files to PDF first.'))
    try:
        if ext == 'pdf':
            reader = PdfReader(upload)
            if reader.is_encrypted:
                raise forms.ValidationError(_('This PDF is password-protected. Remove the password and upload again.'))
            n = len(reader.pages)
        else:
            Image.open(upload).verify()
            n = 1
    except (PdfReadError, UnidentifiedImageError, OSError, ValueError):
        raise forms.ValidationError(_('Could not read this file. Is it a valid PDF or image?'))
    finally:
        upload.seek(0)
    if n == 0:
        raise forms.ValidationError(_('This file has no pages.'))
    return n


def parse_page_range(text, page_count):
    """'1-3, 5' -> sorted list of page numbers. Empty text means every page."""
    text = (text or '').replace(' ', '')
    if not text:
        return list(range(1, page_count + 1))
    if not re.fullmatch(r'\d+(-\d+)?(,\d+(-\d+)?)*', text):
        raise forms.ValidationError(_('Use page numbers and ranges like 1-5, 8, 10-12.'))
    pages = set()
    for part in text.split(','):
        a, _sep, b = part.partition('-')
        a, b = int(a), int(b or a)
        if a < 1 or b < a or b > page_count:
            raise forms.ValidationError(_('Pages must be between 1 and %(page_count)s.') % {'page_count': page_count})
        pages.update(range(a, b + 1))
    return sorted(pages)


class OrderOptionsForm(forms.ModelForm):
    """Step 1: a document with print options, stationery, or both."""

    MAX_QTY = 20

    upload = forms.FileField(label=_('Document'), required=False,
                             widget=forms.ClearableFileInput(attrs={'accept': '.pdf,image/jpeg,image/png'}))

    class Meta:
        model = PrintOrder
        fields = ['color', 'sides', 'copies', 'paper_size', 'binding', 'page_range', 'note']
        widgets = {
            'color': forms.RadioSelect, 'sides': forms.RadioSelect, 'paper_size': forms.RadioSelect,
            'binding': forms.RadioSelect,
            'copies': forms.NumberInput(attrs={'min': 1, 'max': 50, 'inputmode': 'numeric'}),
            'page_range': forms.TextInput(attrs={'placeholder': _('All pages')}),
            'note': forms.TextInput(attrs={'placeholder': _('Optional note for the shop')}),
        }
        labels = {'color': _('Colour')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('color', 'sides', 'paper_size', 'binding'):
            self.fields[name].choices = [c for c in self.fields[name].choices if c[0]]
        current = {line.item_id: line.quantity for line in self.instance.lines.all()} if self.instance.pk else {}
        self.items = list(self.instance.shop.stationery.filter(in_stock=True))
        for item in self.items:
            self.fields[f'qty_{item.pk}'] = forms.IntegerField(
                min_value=0, max_value=self.MAX_QTY, required=False, initial=current.get(item.pk, 0),
                widget=forms.NumberInput(attrs={'min': 0, 'max': self.MAX_QTY, 'inputmode': 'numeric',
                                                'data-price': item.price}))

    @property
    def stationery_fields(self):
        return [(item, self[f'qty_{item.pk}']) for item in self.items]

    def clean_copies(self):
        copies = self.cleaned_data['copies']
        if not 1 <= copies <= 50:
            raise forms.ValidationError(_('Copies must be between 1 and 50.'))
        return copies

    def clean_upload(self):
        upload = self.cleaned_data.get('upload')
        if not upload:
            return None
        if upload.size > settings.PRINT_MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(_('File must be under %(PRINT_MAX_UPLOAD_MB)s MB.') % {'PRINT_MAX_UPLOAD_MB': settings.PRINT_MAX_UPLOAD_MB})
        self.page_count = count_pages(upload)
        return upload

    def clean(self):
        data = super().clean()
        self.chosen = [(item, data.get(f'qty_{item.pk}') or 0) for item in self.items]
        self.chosen = [(item, q) for item, q in self.chosen if q]
        if self.errors:
            return data
        has_doc = bool(data.get('upload')) or bool(self.instance.file)
        if not has_doc and not self.chosen:
            self.add_error('upload', _('Upload a document to print, or pick some stationery below.'))
            return data
        self.pages = []
        if has_doc:
            page_count = getattr(self, 'page_count', None) or self.instance.page_count
            try:
                self.pages = parse_page_range(data.get('page_range'), page_count)
            except forms.ValidationError as e:
                self.add_error('page_range', e)
        return data

    def save(self, commit=True):
        order = super().save(commit=False)
        upload = self.cleaned_data.get('upload')
        if upload:
            if order.file:
                order.file.delete(save=False)
            order.file = upload
            order.file_name = upload.name[:200]
            order.page_count = self.page_count
        order.page_range = (order.page_range or '').replace(' ', '')
        order.pages_to_print = len(self.pages)
        lines = [OrderLine(item=item, name=item.name, unit_price=item.price, quantity=q) for item, q in self.chosen]
        order.recalc(lines)
        order.save()
        order.lines.all().delete()
        for line in lines:
            line.order = order
        OrderLine.objects.bulk_create(lines)
        return order


class StationeryItemForm(forms.ModelForm):
    class Meta:
        model = StationeryItem
        fields = ['name', 'price', 'in_stock']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('e.g. Classmate notebook, 172 pages')}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': '0.5', 'inputmode': 'decimal'}),
        }
        labels = {'price': _('Price (₹)')}

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < 0:
            raise forms.ValidationError(_('Cannot be negative.'))
        return price


class PaymentForm(forms.ModelForm):
    """Step 2: proof that the student paid the shop's QR, and where to deliver."""

    class Meta:
        model = PrintOrder
        fields = ['payment_screenshot', 'txn_last_digits', 'delivery_point']
        widgets = {
            'payment_screenshot': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'txn_last_digits': forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 6, 'placeholder': _('e.g. 4821')}),
            'delivery_point': forms.RadioSelect,
        }
        labels = {
            'payment_screenshot': _('Payment screenshot'),
            'txn_last_digits': _('Last 4–6 digits of the transaction / UTR ID'),
            'delivery_point': _('Deliver to'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = True
        self.fields['delivery_point'].choices = PrintOrder.DeliveryPoint.choices

    def clean_txn_last_digits(self):
        v = self.cleaned_data['txn_last_digits'].strip()
        if not re.fullmatch(r'\d{4,6}', v):
            raise forms.ValidationError(_('Enter the last 4 to 6 digits (numbers only).'))
        return v

    def clean_payment_screenshot(self):
        shot = self.cleaned_data.get('payment_screenshot')
        if shot and hasattr(shot, 'content_type'):
            if shot.size > 10 * 1024 * 1024:
                raise forms.ValidationError(_('Screenshot must be under 10 MB.'))
            return compress_image(shot)
        return shot


class RejectForm(forms.Form):
    reason = forms.CharField(max_length=200, widget=forms.TextInput(
        attrs={'placeholder': _('e.g. Payment not received')}))


class ShopSettingsForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'location', 'phone', 'qr_image', 'upi_id',
                  'bw_single', 'bw_double', 'color_single', 'color_double', 'a3_multiplier',
                  'staple_price', 'spiral_price', 'hard_binding_price', 'delivery_charge']
        widgets = {'qr_image': forms.ClearableFileInput(attrs={'accept': 'image/*'})}

    def clean(self):
        data = super().clean()
        for name, value in data.items():
            if hasattr(value, 'is_signed') and value < 0:
                self.add_error(name, 'Cannot be negative.')
        return data
