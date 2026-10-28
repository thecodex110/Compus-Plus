from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from services.models import ServiceRequest

from .forms import LoginForm, OTPForm, ProfileForm, SignupForm
from .models import User
from .otp import send_otp, verify_otp

PENDING_KEY = 'pending_signup'
LOGIN_MAX_FAILS = 10
LOGIN_LOCK_SECONDS = 15 * 60


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        # Keep the details in the session until the email is verified; the
        # password is hashed right away so it never sits in the session as text.
        request.session[PENDING_KEY] = {
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'role': data['role'],
            'department': data['department'],
            'year': data['year'],
            'password_hash': make_password(data['password']),
        }
        send_otp(data['email'])
        return redirect('accounts:verify')
    return render(request, 'accounts/signup.html', {'form': form})


def verify(request):
    pending = request.session.get(PENDING_KEY)
    if not pending:
        return redirect('accounts:signup')
    form = OTPForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ok, error = verify_otp(pending['email'], form.cleaned_data['code'])
        if ok:
            if User.objects.filter(email=pending['email']).exists():
                messages.error(request, 'This email is already registered. Please log in.')
                del request.session[PENDING_KEY]
                return redirect('accounts:login')
            user = User(
                email=pending['email'], name=pending['name'], phone=pending['phone'],
                role=pending['role'], department=pending['department'], year=pending['year'],
                password=pending['password_hash'],
            )
            user.save()
            del request.session[PENDING_KEY]
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome, {user.get_short_name()}!')
            return redirect('home')
        form.add_error('code', error)
    return render(request, 'accounts/verify.html', {'form': form, 'email': pending['email']})


@require_POST
def resend(request):
    pending = request.session.get(PENDING_KEY)
    if pending:
        send_otp(pending['email'])
        messages.info(request, 'A new code has been sent.')
    return redirect('accounts:verify')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        key = f"login-fail:{email}:{request.META.get('REMOTE_ADDR', '')}"
        if cache.get(key, 0) >= LOGIN_MAX_FAILS:
            form.add_error(None, 'Too many wrong attempts. Wait 15 minutes or reset your password.')
            return render(request, 'accounts/login.html', {'form': form})
        user = authenticate(request, username=email, password=form.cleaned_data['password'])
        if user is None:
            cache.set(key, cache.get(key, 0) + 1, LOGIN_LOCK_SECONDS)
            form.add_error(None, 'Wrong email or password.')
        else:
            cache.delete(key)
            login(request, user)
            nxt = request.GET.get('next', '')
            if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
                return redirect(nxt)
            return redirect('home')
    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def home(request):
    user = request.user
    if user.is_bvg:
        return redirect('services:queue')
    if user.role == User.Role.SHOP:
        return redirect('printing:shop_dashboard')
    if user.is_admin_role:
        return redirect('panel:dashboard')
    if user.is_requester:
        recent = ServiceRequest.objects.filter(user=user).select_related('location')[:5]
        return render(request, 'accounts/home.html', {'recent': recent})
    return render(request, 'accounts/home_other.html')


@login_required
def profile(request):
    user = request.user
    details = ProfileForm(request.POST if request.POST.get('form') == 'details' else None, instance=user)
    password = PasswordChangeForm(user, request.POST if request.POST.get('form') == 'password' else None)
    if request.method == 'POST':
        if request.POST.get('form') == 'details' and details.is_valid():
            details.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
        if request.POST.get('form') == 'password' and password.is_valid():
            password.save()
            update_session_auth_hash(request, password.user)
            messages.success(request, 'Password changed.')
            return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {'details': details, 'password': password})
