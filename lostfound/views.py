from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import PostForm
from .models import Post

R = User.Role
USERS = (R.STUDENT, R.TEACHER, R.ADMIN)


@role_required(*USERS)
def feed(request):
    qs = Post.objects.filter(status=Post.Status.OPEN).select_related('user')
    kind = request.GET.get('type')
    if kind in Post.Type.values:
        qs = qs.filter(type=kind)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(place__icontains=q))
    page = Paginator(qs, 12).get_page(request.GET.get('page'))
    return render(request, 'lostfound/feed.html', {
        'page': page, 'kind': kind, 'q': q, 'types': Post.Type.choices,
    })


@role_required(*USERS)
def new_post(request):
    form = PostForm(request.POST or None, request.FILES or None,
                    initial={'type': request.GET.get('type', Post.Type.FOUND)})
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.user = request.user
        post.save()
        messages.success(request, 'Posted to Lost & Found.')
        return redirect('lostfound:detail', pk=post.pk)
    return render(request, 'lostfound/form.html', {'form': form})


@role_required(*USERS)
def detail(request, pk):
    post = get_object_or_404(Post.objects.select_related('user'), pk=pk)
    is_owner = post.user_id == request.user.pk
    if post.status == Post.Status.REMOVED and not (is_owner or request.user.is_admin_role):
        raise PermissionDenied
    return render(request, 'lostfound/detail.html', {'post': post, 'is_owner': is_owner})


@role_required(*USERS)
def my_posts(request):
    qs = Post.objects.filter(user=request.user).exclude(status=Post.Status.REMOVED)
    return render(request, 'lostfound/mine.html', {'posts': qs})


@require_POST
@role_required(*USERS)
def mark_returned(request, pk):
    post = get_object_or_404(Post, pk=pk, user=request.user, status=Post.Status.OPEN)
    post.status = Post.Status.RETURNED
    post.returned_at = timezone.now()
    post.save(update_fields=['status', 'returned_at'])
    messages.success(request, 'Marked as returned and removed from the feed. 🎉')
    return redirect('lostfound:mine')


@require_POST
@role_required(R.ADMIN)
def remove(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.status = Post.Status.REMOVED
    post.save(update_fields=['status'])
    messages.success(request, 'Post removed from the feed.')
    return redirect('lostfound:feed')
