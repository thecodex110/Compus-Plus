from django import forms
from django.conf import settings
from django.contrib.auth import password_validation

from .models import User


def is_coep_email(email):
    domain = email.rsplit('@', 1)[-1].lower()
    return domain in settings.ALLOWED_EMAIL_DOMAINS


class SignupForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField(help_text='Use your college email.')
    phone = forms.RegexField(regex=r'^[6-9]\d{9}$', max_length=10,
                             error_messages={'invalid': 'Enter a 10-digit mobile number.'})
    role = forms.ChoiceField(choices=[(r.value, r.label) for r in User.SELF_SIGNUP_ROLES])
    department = forms.CharField(max_length=80)
    year = forms.TypedChoiceField(choices=[('', '—')] + [(i, f'Year {i}') for i in range(1, 6)],
                                  coerce=int, required=False, empty_value=None)
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm password')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if not is_coep_email(email):
            domains = ', '.join('@' + d for d in settings.ALLOWED_EMAIL_DOMAINS)
            raise forms.ValidationError(f'Only COEP emails ({domains}) can sign up.')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        data = super().clean()
        if data.get('role') == User.Role.STUDENT and not data.get('year'):
            self.add_error('year', 'Students must pick their year.')
        p1, p2 = data.get('password'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match.')
        if p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as e:
                self.add_error('password', e)
        return data


class OTPForm(forms.Form):
    code = forms.RegexField(regex=r'^\d{6}$', max_length=6, label='6-digit code',
                            error_messages={'invalid': 'Enter the 6-digit code.'},
                            widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}))


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
