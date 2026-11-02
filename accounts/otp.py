import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import EmailOTP


def send_otp(email):
    code = f'{secrets.randbelow(1_000_000):06d}'
    EmailOTP.objects.filter(email=email, used=False).update(used=True)
    EmailOTP.objects.create(email=email, code_hash=make_password(code))
    send_mail(
        _('Your Campus Plus code'),
        _('Your verification code is %(code)s. It expires in %(minutes)s minutes.') % {
            'code': code, 'minutes': settings.OTP_TTL_MINUTES},
        None,
        [email],
    )


def verify_otp(email, code):
    """Return (ok, error_message)."""
    otp = EmailOTP.objects.filter(email=email, used=False).first()
    if otp is None:
        return False, _('No active code. Request a new one.')
    if timezone.now() - otp.created_at > timedelta(minutes=settings.OTP_TTL_MINUTES):
        return False, _('Code expired. Request a new one.')
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        return False, _('Too many attempts. Request a new code.')
    otp.attempts += 1
    if not check_password(code, otp.code_hash):
        otp.save(update_fields=['attempts'])
        return False, _('Incorrect code.')
    otp.used = True
    otp.save(update_fields=['attempts', 'used'])
    return True, ''
