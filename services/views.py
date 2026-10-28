from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import ServiceRequestForm
from .models import Location, ServiceRequest

R = User.Role
S = ServiceRequest.Status


def location_tree():
    """{building: {floor: [[id, classroom], ...]}} for the chained pickers."""
    tree = {}
    for loc in Location.objects.all():
        tree.setdefault(loc.building, {}).setdefault(loc.floor, []).append([loc.pk, loc.classroom])
    return tree


@role_required(R.STUDENT, R.TEACHER)
def new_request(request):
    last = ServiceRequest.objects.filter(user=request.user).only('location').first()
    initial = {'category': request.GET.get('category'), 'location': last.location_id if last else None}
    form = ServiceRequestForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        sr = form.save(commit=False)
        sr.user = request.user
        sr.save()
        messages.success(request, f'Request #{sr.pk} sent to BVG staff.')
        return redirect('services:detail', pk=sr.pk)
    selected = form['location'].value()
    selected_loc = Location.objects.filter(pk=selected).first() if selected else None
    return render(request, 'services/new.html', {
        'form': form,
        'tree': location_tree(),
        'selected_loc': selected_loc,
        'high': ServiceRequest.HIGH_PRIORITY_CATEGORIES,
    })


@role_required(R.STUDENT, R.TEACHER)
def my_requests(request):
    qs = ServiceRequest.objects.filter(user=request.user).select_related('location', 'assigned_staff')
    return render(request, 'services/list.html', {
        'title': 'My requests', 'requests': qs.order_by('-created_at'), 'poll': 'mine',
    })


@login_required
def detail(request, pk):
    sr = get_object_or_404(ServiceRequest.objects.select_related('user', 'location', 'assigned_staff'), pk=pk)
    user = request.user
    if not (sr.user_id == user.pk or user.is_bvg or user.is_admin_role):
        raise PermissionDenied
    return render(request, 'services/detail.html', {
        'sr': sr,
        'events': sr.events.select_related('by'),
        'can_advance': user.is_bvg and sr.next_status
                       and (sr.status == S.PENDING or sr.assigned_staff_id == user.pk),
        'poll': f'one:{sr.pk}',
    })


@role_required(R.BVG)
def queue(request):
    qs = ServiceRequest.objects.filter(status=S.PENDING).select_related('location', 'user')
    return render(request, 'services/list.html', {
        'title': 'Open queue', 'requests': qs, 'staff_view': True, 'poll': 'queue',
        'empty': 'No pending requests right now.',
    })


@role_required(R.BVG)
def my_jobs(request):
    qs = ServiceRequest.objects.filter(assigned_staff=request.user, status__in=[S.ACCEPTED, S.IN_PROGRESS])
    return render(request, 'services/list.html', {
        'title': 'My jobs', 'requests': qs.select_related('location', 'user'), 'staff_view': True,
        'poll': 'jobs', 'empty': 'You have no active jobs.',
    })


@role_required(R.BVG, R.ADMIN)
def history(request):
    qs = ServiceRequest.objects.select_related('location', 'user', 'assigned_staff')
    if request.user.is_bvg:
        qs = qs.filter(assigned_staff=request.user)
        title = 'My history'
    else:
        title = 'All requests'
    status = request.GET.get('status')
    if status in S.values:
        qs = qs.filter(status=status)
    return render(request, 'services/list.html', {
        'title': title, 'requests': qs.order_by('-created_at')[:200], 'staff_view': True,
        'statuses': S.choices, 'current_status': status, 'empty': 'Nothing here yet.',
    })


@require_POST
@role_required(R.BVG)
def advance(request, pk):
    with transaction.atomic():
        # Lock the row so two staff cannot accept the same request at once.
        sr = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=pk)
        before = sr.status
        if sr.advance(request.user):
            messages.success(request, f'#{sr.pk} marked {sr.get_status_display()}.')
        elif before == S.PENDING or sr.assigned_staff_id != request.user.pk:
            messages.error(request, f'#{sr.pk} was already taken by someone else.')
        else:
            messages.error(request, 'That request cannot move further.')
    nxt = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect('services:detail', pk=pk)


@login_required
def poll(request):
    """A cheap fingerprint; the page reloads itself when it changes."""
    scope = request.GET.get('scope', '')
    user = request.user
    qs = ServiceRequest.objects.none()
    if scope == 'mine' and user.is_requester:
        qs = ServiceRequest.objects.filter(user=user)
    elif scope == 'queue' and user.is_bvg:
        qs = ServiceRequest.objects.filter(status=S.PENDING)
    elif scope == 'jobs' and user.is_bvg:
        qs = ServiceRequest.objects.filter(assigned_staff=user)
    elif scope.startswith('one:'):
        pk = scope[4:]
        qs = ServiceRequest.objects.filter(pk=pk if pk.isdigit() else 0)
        if not (user.is_bvg or user.is_admin_role):
            qs = qs.filter(user=user)
    agg = qs.aggregate(m=Max('updated_at'))
    return JsonResponse({'v': f"{qs.count()}:{agg['m'].timestamp() if agg['m'] else 0}"})
