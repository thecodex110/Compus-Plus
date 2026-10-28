from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import DonorForm
from .models import COMPATIBLE_DONORS, BloodGroup, ContactReveal, Donor, Hospital

R = User.Role
SEARCHERS = (R.STUDENT, R.TEACHER, R.ADMIN)
# How many donor numbers one person can look up per day.
REVEALS_PER_DAY = 15


def _reveals_today(user):
    return ContactReveal.objects.filter(viewer=user, at__gte=timezone.now() - timedelta(days=1)).count()


@role_required(*SEARCHERS)
def directory(request):
    group = request.GET.get('group')
    compatible = request.GET.get('compatible') == '1'
    donors = None
    if group in BloodGroup.values:
        groups = COMPATIBLE_DONORS[group] if compatible else [group]
        donors = (Donor.objects.filter(visible=True, blood_group__in=groups, user__is_active=True)
                  .exclude(user=request.user).select_related('user'))
        donors = sorted(donors, key=lambda d: (d.blood_group != group, d.recently_donated, d.user.name))
    revealed = set(ContactReveal.objects.filter(viewer=request.user, at__gte=timezone.now() - timedelta(days=1))
                   .values_list('donor_id', flat=True))
    me = Donor.objects.filter(user=request.user).first() if request.user.role == R.STUDENT else None
    return render(request, 'health/directory.html', {
        'groups': BloodGroup.choices, 'group': group, 'compatible': compatible, 'donors': donors,
        'compatible_list': COMPATIBLE_DONORS.get(group, []), 'revealed': revealed, 'me': me,
    })


@require_POST
@role_required(*SEARCHERS)
def reveal(request, pk):
    donor = get_object_or_404(Donor, pk=pk, visible=True, user__is_active=True)
    # Only ever send people back to the directory page they came from.
    back = request.POST.get('back', '')
    if not back.startswith('/blood/?') or '//' in back:
        back = '/blood/'
    already = ContactReveal.objects.filter(viewer=request.user, donor=donor,
                                           at__gte=timezone.now() - timedelta(days=1)).exists()
    if not already:
        if _reveals_today(request.user) >= REVEALS_PER_DAY:
            messages.error(request, f'You can view at most {REVEALS_PER_DAY} numbers a day. '
                                    'For a real emergency call 108 or the hospital blood bank.')
            return redirect(back)
        ContactReveal.objects.create(viewer=request.user, donor=donor)
    return redirect(f'{back}#donor-{donor.pk}')


@role_required(R.STUDENT)
def my_entry(request):
    donor = Donor.objects.filter(user=request.user).first()
    form = DonorForm(request.POST or None, instance=donor or Donor(user=request.user))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Saved. You are listed in the blood directory.' if form.instance.visible
                         else 'Saved. You are hidden from the directory.')
        return redirect('health:me')
    recent = donor.reveals.select_related('viewer')[:20] if donor else []
    return render(request, 'health/me.html', {'form': form, 'donor': donor, 'recent': recent})


@require_POST
@role_required(R.STUDENT)
def toggle_visible(request):
    donor = get_object_or_404(Donor, user=request.user)
    donor.visible = not donor.visible
    donor.save(update_fields=['visible', 'updated_at'])
    messages.success(request, 'You are now listed in the directory.' if donor.visible
                     else 'You are now hidden. Nobody can see your blood group or number.')
    return redirect('health:me')


@require_POST
@role_required(R.STUDENT)
def delete_entry(request):
    Donor.objects.filter(user=request.user).delete()
    messages.success(request, 'Your blood group entry has been deleted.')
    return redirect('health:me')


@login_required
def hospitals(request):
    qs = Hospital.objects.all()
    if request.GET.get('blood_bank') == '1':
        qs = qs.filter(has_blood_bank=True)
    return render(request, 'health/hospitals.html', {'hospitals': qs, 'blood_bank': request.GET.get('blood_bank') == '1'})
