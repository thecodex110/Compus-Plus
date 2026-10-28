from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import ListingForm
from .models import Listing, ListingPhoto

R = User.Role
USERS = (R.STUDENT, R.ADMIN)
SORTS = {
    'new': ('Newest', ['-created_at']),
    'low': ('Price: low to high', ['price', '-created_at']),
    'high': ('Price: high to low', ['-price', '-created_at']),
}


def with_photos(qs):
    return qs.prefetch_related(Prefetch('photos', queryset=ListingPhoto.objects.order_by('position', 'pk')))


def _int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


@role_required(*USERS)
def browse(request):
    qs = Listing.objects.filter(status=Listing.Status.AVAILABLE).select_related('seller')
    g = request.GET
    q = g.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    category = g.get('category')
    if category in Listing.Category.values:
        qs = qs.filter(category=category)
    condition = g.get('condition')
    if condition in Listing.Condition.values:
        qs = qs.filter(condition=condition)
    pmin, pmax = _int(g.get('min')), _int(g.get('max'))
    if pmin is not None:
        qs = qs.filter(price__gte=pmin)
    if pmax is not None:
        qs = qs.filter(price__lte=pmax)
    sort = g.get('sort') if g.get('sort') in SORTS else 'new'
    qs = with_photos(qs.order_by(*SORTS[sort][1]))

    # Query string without "page", for pagination links.
    params = g.copy()
    params.pop('page', None)
    return render(request, 'market/browse.html', {
        'page': Paginator(qs, 20).get_page(g.get('page')),
        'q': q, 'category': category, 'condition': condition, 'pmin': pmin, 'pmax': pmax, 'sort': sort,
        'categories': Listing.Category.choices, 'conditions': Listing.Condition.choices,
        'sorts': [(k, v[0]) for k, v in SORTS.items()], 'params': params.urlencode(),
        'filtered': bool(condition or pmin is not None or pmax is not None or sort != 'new'),
    })


@role_required(*USERS)
def detail(request, pk):
    listing = get_object_or_404(with_photos(Listing.objects.select_related('seller')), pk=pk)
    is_owner = listing.seller_id == request.user.pk
    if listing.status == Listing.Status.REMOVED and not (is_owner or request.user.is_admin_role):
        raise PermissionDenied
    return render(request, 'market/detail.html', {'listing': listing, 'is_owner': is_owner})


@role_required(R.STUDENT)
def sell(request):
    form = ListingForm(request.POST or None, request.FILES or None, instance=Listing(seller=request.user))
    if request.method == 'POST' and form.is_valid():
        listing = form.save()
        messages.success(request, 'Your item is live on COEP Market.')
        return redirect('market:detail', pk=listing.pk)
    return render(request, 'market/form.html', {'form': form})


@role_required(R.STUDENT)
def edit(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user, status=Listing.Status.AVAILABLE)
    form = ListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Listing updated.')
        return redirect('market:detail', pk=pk)
    return render(request, 'market/form.html', {'form': form, 'listing': listing})


@role_required(R.STUDENT)
def mine(request):
    qs = with_photos(Listing.objects.filter(seller=request.user).exclude(status=Listing.Status.REMOVED))
    return render(request, 'market/mine.html', {'listings': qs})


@require_POST
@role_required(R.STUDENT)
def mark_sold(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user, status=Listing.Status.AVAILABLE)
    listing.status = Listing.Status.SOLD
    listing.sold_at = timezone.now()
    listing.save(update_fields=['status', 'sold_at', 'updated_at'])
    messages.success(request, 'Marked as sold. 🎉')
    return redirect('market:mine')


@require_POST
@role_required(R.STUDENT)
def delete(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    for photo in listing.photos.all():
        photo.delete()
    listing.delete()
    messages.success(request, 'Listing deleted.')
    return redirect('market:mine')


@require_POST
@role_required(R.ADMIN)
def remove(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    listing.status = Listing.Status.REMOVED
    listing.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Listing removed from the market.')
    return redirect('market:browse')
