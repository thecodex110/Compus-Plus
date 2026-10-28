from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from services.models import ServiceRequest

from .forms import LoginForm, OTPForm, SignupForm
from .models import User
from .otp import send_otp, verify_otp

PENDING_KEY = 'pending_signup'


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
        user = authenticate(request, username=form.cleaned_data['email'].lower(),
                            password=form.cleaned_data['password'])
        if user is None:
            form.add_error(None, 'Wrong email or password.')
        else:
            login(request, user)
            return redirect(request.GET.get('next') or 'home')
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
    if user.is_admin_role:
        counts = {s.label: ServiceRequest.objects.filter(status=s).count()
                  for s in ServiceRequest.Status}
        return render(request, 'accounts/home_admin.html', {'counts': counts})
    if user.is_requester:
        recent = ServiceRequest.objects.filter(user=user).select_related('location')[:5]
        return render(request, 'accounts/home.html', {'recent': recent})
    return render(request, 'accounts/home_other.html')
