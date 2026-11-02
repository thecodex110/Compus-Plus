from collections import OrderedDict
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from accounts.decorators import role_required
from accounts.models import User
from health.models import Donor, Hospital
from lostfound.models import Post
from market.models import Listing
from printing.models import PrintOrder, Shop
from services.models import Location, ServiceRequest, floor_key

from .forms import BulkLocationForm, CreateUserForm, HospitalForm, ShopAdminForm

admin_only = role_required(User.Role.ADMIN)
SR = ServiceRequest.Status


@admin_only
def dashboard(request):
    now = timezone.now()
    week = now - timedelta(days=7)
    open_requests = ServiceRequest.objects.filter(status__in=ServiceRequest.OPEN_STATUSES)
    stats = [
        (_('Open service requests'), open_requests.count(), 'services:history'),
        (_('…of which high priority'), open_requests.filter(priority=ServiceRequest.Priority.HIGH).count(), None),
        (_('Requests this week'), ServiceRequest.objects.filter(created_at__gte=week).count(), None),
        (_('Active print orders'), PrintOrder.objects.filter(status__in=PrintOrder.ACTIVE).count(), None),
        (_('Open Lost & Found posts'), Post.objects.filter(status=Post.Status.OPEN).count(), 'panel:moderate'),
        (_('Items for sale'), Listing.objects.filter(status=Listing.Status.AVAILABLE).count(), 'panel:moderate'),
        (_('Listed blood donors'), Donor.objects.filter(visible=True).count(), None),
        (_('Shops open now'), Shop.objects.filter(is_open=True).count(), None),
    ]
    roles = OrderedDict((label, 0) for _value, label in User.Role.choices)
    for row in User.objects.filter(is_active=True).values('role').annotate(n=Count('id')):
        roles[User.Role(row['role']).label] = row['n']
    # Requests waiting for a long time are the ones an admin should chase.
    stale = (open_requests.filter(status=SR.PENDING, created_at__lt=now - timedelta(minutes=15))
             .select_related('location', 'user')[:10])
    return render(request, 'panel/dashboard.html', {
        'stats': stats, 'roles': roles, 'stale': stale,
        'shops': Shop.objects.all(),
    })


@admin_only
def users(request):
    qs = User.objects.order_by('role', 'name')
    role = request.GET.get('role')
    if role in User.Role.values:
        qs = qs.filter(role=role)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    return render(request, 'panel/users.html', {
        'page': Paginator(qs, 30).get_page(request.GET.get('page')),
        'roles': User.Role.choices, 'role': role, 'q': q,
    })


@admin_only
def create_user(request):
    form = CreateUserForm(request.POST or None, initial={'role': request.GET.get('role', User.Role.BVG)})
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if user.role == User.Role.SHOP:
            Shop.objects.get_or_create(owner=user, defaults={'name': user.name, 'phone': user.phone})
        messages.success(request, _('%(get_role_display)s account created for %(email)s.') % {'get_role_display': user.get_role_display(), 'email': user.email})
        return redirect('panel:users')
    return render(request, 'panel/user_form.html', {'form': form})


@require_POST
@admin_only
def toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, _("You can't deactivate your own account."))
    else:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        if not user.is_active and user.role == User.Role.SHOP:
            Shop.objects.filter(owner=user).update(is_open=False)
        msg = _('%(email)s activated.') if user.is_active else _('%(email)s deactivated.')
        messages.success(request, msg % {'email': user.email})
    return redirect(request.POST.get('back') if (request.POST.get('back') or '').startswith('/admin-panel/') else 'panel:users')


@admin_only
def locations(request):
    form = BulkLocationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        added = form.save()
        messages.success(request, ngettext('%(n)s classroom added.', '%(n)s classrooms added.', added) % {'n': added})
        return redirect('panel:locations')
    tree = OrderedDict()
    for loc in Location.objects.annotate(n=Count('requests')):
        tree.setdefault(loc.building, OrderedDict()).setdefault(loc.floor, []).append(loc)
    tree = OrderedDict((b, OrderedDict(sorted(floors.items(), key=lambda kv: floor_key(kv[0]))))
                       for b, floors in tree.items())
    return render(request, 'panel/locations.html', {'form': form, 'tree': tree})


@require_POST
@admin_only
def delete_location(request, pk):
    loc = get_object_or_404(Location, pk=pk)
    try:
        loc.delete()
        messages.success(request, _('Removed %(loc)s.') % {'loc': loc})
    except ProtectedError:
        messages.error(request, _('%(loc)s has service requests in its history, so it cannot be removed.') % {'loc': loc})
    return redirect('panel:locations')


@admin_only
def hospitals(request):
    return render(request, 'panel/hospitals.html', {'hospitals': Hospital.objects.all()})


@admin_only
def hospital_form(request, pk=None):
    hospital = get_object_or_404(Hospital, pk=pk) if pk else None
    form = HospitalForm(request.POST or None, instance=hospital)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Hospital saved.'))
        return redirect('panel:hospitals')
    return render(request, 'panel/hospital_form.html', {'form': form, 'hospital': hospital})


@require_POST
@admin_only
def delete_hospital(request, pk):
    get_object_or_404(Hospital, pk=pk).delete()
    messages.success(request, _('Hospital removed.'))
    return redirect('panel:hospitals')


@admin_only
def moderate(request):
    return render(request, 'panel/moderate.html', {
        'posts': Post.objects.filter(status=Post.Status.OPEN).select_related('user')[:50],
        'listings': Listing.objects.filter(status=Listing.Status.AVAILABLE).select_related('seller')
                    .prefetch_related('photos')[:50],
    })


@require_POST
@admin_only
def remove_item(request, kind, pk):
    if kind == 'post':
        Post.objects.filter(pk=pk).update(status=Post.Status.REMOVED)
    elif kind == 'listing':
        Listing.objects.filter(pk=pk).update(status=Listing.Status.REMOVED)
    messages.success(request, _('Removed.'))
    return redirect('panel:moderate')


@admin_only
def shops(request):
    qs = Shop.objects.select_related('owner').annotate(
        active=Count('orders', filter=Q(orders__status__in=PrintOrder.ACTIVE), distinct=True),
        delivered=Count('orders', filter=Q(orders__status=PrintOrder.Status.DELIVERED), distinct=True),
        items=Count('stationery', distinct=True))
    return render(request, 'panel/shops.html', {'shops': qs})


@admin_only
def shop_edit(request, pk):
    shop = get_object_or_404(Shop.objects.select_related('owner'), pk=pk)
    form = ShopAdminForm(request.POST or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('%(name)s saved.') % {'name': shop.name})
        return redirect('panel:shops')
    return render(request, 'panel/shop_form.html', {'form': form, 'shop': shop})
