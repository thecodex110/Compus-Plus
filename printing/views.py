from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from accounts.decorators import role_required
from accounts.models import User
from notify.models import notify

from .forms import OrderOptionsForm, PaymentForm, RejectForm, ShopSettingsForm, StationeryItemForm
from .models import PrintOrder, Shop, StationeryItem

R = User.Role
S = PrintOrder.Status


def shop_for(user):
    shop, _created = Shop.objects.get_or_create(owner=user, defaults={'name': user.name, 'phone': user.phone})
    return shop


def poll_url(scope):
    return f"{reverse('printing:poll')}?scope={scope}"


# ---------- Student ----------

@role_required(R.STUDENT)
def shops(request):
    return render(request, 'printing/shops.html', {
        'shops': Shop.objects.all(),
        'active': PrintOrder.objects.filter(student=request.user, status__in=PrintOrder.ACTIVE).select_related('shop'),
    })


@role_required(R.STUDENT)
def new_order(request, shop_id):
    shop = get_object_or_404(Shop, pk=shop_id)
    if not shop.accepts_orders:
        messages.error(request, _('%(name)s is closed right now.') % {'name': shop.name})
        return redirect('printing:shops')
    order = PrintOrder(student=request.user, shop=shop)
    form = OrderOptionsForm(request.POST or None, request.FILES or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        order = form.save()
        return redirect('printing:pay', pk=order.pk)
    return render(request, 'printing/options.html', {'form': form, 'shop': shop})


def _student_order(request, pk, **filters):
    return get_object_or_404(PrintOrder.objects.select_related('shop'), pk=pk, student=request.user, **filters)


@role_required(R.STUDENT)
def edit_options(request, pk):
    order = _student_order(request, pk, status=S.DRAFT)
    form = OrderOptionsForm(request.POST or None, request.FILES or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('printing:pay', pk=order.pk)
    return render(request, 'printing/options.html', {'form': form, 'shop': order.shop, 'order': order})


@role_required(R.STUDENT)
def pay(request, pk):
    order = _student_order(request, pk, status=S.DRAFT)
    shop = order.shop
    form = PaymentForm(request.POST or None, request.FILES or None, instance=order)
    if request.method == 'POST':
        if not shop.accepts_orders:
            messages.error(request, _('%(name)s closed before you finished. Pick another shop.') % {'name': shop.name})
            return redirect('printing:shops')
        if form.is_valid():
            order = form.save(commit=False)
            order.status = S.PLACED
            order.placed_at = timezone.now()
            order.save()
            order.log(S.PLACED, request.user)
            notify(shop.owner, lambda: _('New order %(number)s — ₹%(amount)s') % {
                       'number': f'ORD-{order.pk:04d}', 'amount': f'{order.price:.0f}'},
                   lambda: _('%(name)s · txn …%(digits)s · verify the payment') % {
                       'name': request.user.name, 'digits': order.txn_last_digits},
                   reverse('printing:shop_order', args=[order.pk]), urgent=True)
            messages.success(request, _('Order %(number)s placed. %(name)s will verify your payment.') % {'number': f'ORD-{order.pk:04d}', 'name': shop.name})
            return redirect('printing:order', pk=order.pk)
    return render(request, 'printing/pay.html', {'form': form, 'order': order, 'shop': shop})


@require_POST
@role_required(R.STUDENT)
def cancel_draft(request, pk):
    order = _student_order(request, pk, status=S.DRAFT)
    if order.file:
        order.file.delete(save=False)
    order.delete()
    messages.info(request, _('Order discarded.'))
    return redirect('printing:shops')


@role_required(R.STUDENT)
def my_orders(request):
    qs = (PrintOrder.objects.filter(student=request.user).exclude(status=S.DRAFT)
          .select_related('shop').prefetch_related('lines'))
    return render(request, 'printing/my_orders.html', {'orders': qs, 'poll_url': poll_url('mine')})


@role_required(R.STUDENT)
def order_detail(request, pk):
    order = _student_order(request, pk)
    if order.status == S.DRAFT:
        return redirect('printing:pay', pk=pk)
    idx = PrintOrder.TRACKED.index(order.status) if order.status in PrintOrder.TRACKED else -1
    return render(request, 'printing/order.html', {
        'order': order, 'events': order.events.select_related('by'),
        'steps': [(s.label, i <= idx, i == idx and s != S.DELIVERED) for i, s in enumerate(PrintOrder.TRACKED)],
        'poll_url': poll_url(f'one:{pk}'),
    })


# ---------- Shop ----------

@role_required(R.SHOP)
def shop_dashboard(request):
    shop = shop_for(request.user)
    orders = shop.orders.exclude(status=S.DRAFT).select_related('student').prefetch_related('lines')
    tab = request.GET.get('tab', 'new')
    tabs = {
        'new': (_('To verify'), orders.filter(status=S.PLACED).order_by('placed_at')),
        'active': (_('In progress'), orders.filter(status__in=[S.VERIFIED, S.PRINTING, S.OUT]).order_by('placed_at')),
        'done': (_('Done'), orders.filter(status__in=[S.DELIVERED, S.REJECTED]).order_by('-updated_at')[:100]),
    }
    if tab not in tabs:
        tab = 'new'
    return render(request, 'printing/shop_dashboard.html', {
        'shop': shop, 'tab': tab, 'tabs': [(k, v[0], v[1].count() if k != 'done' else None) for k, v in tabs.items()],
        'orders': tabs[tab][1], 'poll_url': poll_url('shop'),
    })


def _shop_order(request, pk):
    return get_object_or_404(PrintOrder.objects.select_related('student', 'shop'),
                             pk=pk, shop__owner=request.user)


@role_required(R.SHOP)
def shop_order(request, pk):
    order = _shop_order(request, pk)
    if order.status == S.DRAFT:
        raise Http404
    return render(request, 'printing/shop_order.html', {
        'order': order, 'events': order.events.select_related('by'), 'reject_form': RejectForm(),
        'poll_url': poll_url(f'one:{pk}'),
    })


@require_POST
@role_required(R.SHOP)
def shop_advance(request, pk):
    with transaction.atomic():
        order = get_object_or_404(PrintOrder.objects.select_for_update(), pk=pk, shop__owner=request.user)
        nxt = order.next_status
        if nxt is None:
            messages.error(request, _('This order cannot move further.'))
            return redirect('printing:shop_order', pk=pk)
        order.status = nxt
        order.save(update_fields=['status', 'updated_at'])
        order.log(nxt, request.user)
        body = ((lambda: _('Collect it at the %(place)s.') % {'place': order.get_delivery_point_display()})
                if nxt == S.OUT else f'{order.shop.name} · {order.summary}')
        notify(order.student, lambda: _('Order %(number)s: %(status)s') % {
                   'number': f'ORD-{order.pk:04d}', 'status': order.get_status_display()}, body,
               reverse('printing:order', args=[order.pk]), urgent=nxt == S.OUT)
    if nxt == S.DELIVERED:
        order.delete_print_file()
    messages.success(request, _('Order %(number)s: %(get_status_display)s.') % {'number': f'ORD-{pk:04d}', 'get_status_display': order.get_status_display()})
    return redirect('printing:shop_order', pk=pk)


@require_POST
@role_required(R.SHOP)
def shop_reject(request, pk):
    order = _shop_order(request, pk)
    form = RejectForm(request.POST)
    if order.status != S.PLACED or not form.is_valid():
        messages.error(request, _('Only new orders can be rejected, with a reason.'))
        return redirect('printing:shop_order', pk=pk)
    order.status = S.REJECTED
    order.reject_reason = form.cleaned_data['reason']
    order.save(update_fields=['status', 'reject_reason', 'updated_at'])
    order.log(S.REJECTED, request.user, order.reject_reason)
    notify(order.student, lambda: _('Order %(number)s was rejected') % {'number': f'ORD-{order.pk:04d}'},
           order.reject_reason,
           reverse('printing:order', args=[order.pk]), urgent=True)
    order.delete_print_file()
    messages.success(request, _('Order %(number)s rejected.') % {'number': f'ORD-{pk:04d}'})
    return redirect('printing:shop_dashboard')


@require_POST
@role_required(R.SHOP)
def toggle_open(request):
    shop = shop_for(request.user)
    if not shop.is_open and not shop.qr_image:
        messages.error(request, _('Upload your payment QR code in Settings before opening.'))
        return redirect('printing:shop_settings')
    shop.is_open = not shop.is_open
    shop.save(update_fields=['is_open'])
    messages.success(request, _('Shop is now open.') if shop.is_open else _('Shop is now closed.'))
    return redirect('printing:shop_dashboard')


@role_required(R.SHOP)
def shop_settings(request):
    shop = shop_for(request.user)
    form = ShopSettingsForm(request.POST or None, request.FILES or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Settings saved.'))
        return redirect('printing:shop_settings')
    return render(request, 'printing/shop_settings.html', {'form': form, 'shop': shop})


@role_required(R.SHOP)
def shop_stationery(request):
    shop = shop_for(request.user)
    form = StationeryItemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.shop = shop
        item.save()
        messages.success(request, _('Added %(name)s.') % {'name': item.name})
        return redirect('printing:shop_stationery')
    return render(request, 'printing/shop_stationery.html', {
        'shop': shop, 'form': form, 'items': shop.stationery.all(),
    })


@require_POST
@role_required(R.SHOP)
def stationery_update(request, pk):
    item = get_object_or_404(StationeryItem, pk=pk, shop__owner=request.user)
    action = request.POST.get('action')
    if action == 'toggle':
        item.in_stock = not item.in_stock
        item.save(update_fields=['in_stock'])
    elif action == 'delete':
        item.delete()
        messages.success(request, _('Removed %(name)s.') % {'name': item.name})
    elif action == 'price':
        form = StationeryItemForm({'name': item.name, 'price': request.POST.get('price'),
                                   'in_stock': item.in_stock}, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, _('%(name)s: ₹%(price)s.') % {'name': item.name, 'price': item.price})
        else:
            messages.error(request, _('Enter a valid price.'))
    return redirect('printing:shop_stationery')


# ---------- Shared ----------

@role_required(R.STUDENT, R.SHOP)
def download(request, pk, kind):
    """Serve a private file to the order's student or its shop only."""
    order = get_object_or_404(PrintOrder, pk=pk)
    user = request.user
    if not (order.student_id == user.pk or order.shop.owner_id == user.pk):
        raise PermissionDenied
    f = {'file': order.file, 'screenshot': order.payment_screenshot}.get(kind)
    if not f:
        raise Http404('File no longer available.')
    name = order.file_name if kind == 'file' else f'payment-{order.pk}.jpg'
    inline = request.GET.get('dl') != '1'
    return FileResponse(f.open('rb'), as_attachment=not inline, filename=name)


@role_required(R.STUDENT, R.SHOP)
def poll(request):
    scope = request.GET.get('scope', '')
    user = request.user
    qs = PrintOrder.objects.none()
    if scope == 'mine' and user.role == R.STUDENT:
        qs = PrintOrder.objects.filter(student=user)
    elif scope == 'shop' and user.role == R.SHOP:
        qs = PrintOrder.objects.filter(shop__owner=user).exclude(status=S.DRAFT)
    elif scope.startswith('one:') and scope[4:].isdigit():
        qs = PrintOrder.objects.filter(pk=scope[4:])
        qs = qs.filter(student=user) if user.role == R.STUDENT else qs.filter(shop__owner=user)
    m = qs.aggregate(m=Max('updated_at'))['m']
    return JsonResponse({'v': f'{qs.count()}:{m.timestamp() if m else 0}'})
