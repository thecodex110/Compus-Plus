from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def inbox(request):
    items = list(request.user.notifications.all()[:50])
    request.user.notifications.filter(read=False).update(read=True)
    return render(request, 'notify/inbox.html', {'items': items})


@login_required
def open_one(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.read:
        n.read = True
        n.save(update_fields=['read'])
    if n.url and url_has_allowed_host_and_scheme(n.url, allowed_hosts={request.get_host()}):
        return redirect(n.url)
    return redirect('notify:inbox')


@require_POST
@login_required
def mark_all_read(request):
    request.user.notifications.filter(read=False).update(read=True)
    return redirect('notify:inbox')


@login_required
def poll(request):
    """Unread count plus the newest unread item, for the bell and browser alerts."""
    unread = request.user.notifications.filter(read=False)
    latest = unread.first()
    return JsonResponse({
        'unread': unread.count(),
        'latest': latest and {'id': latest.pk, 'title': latest.title, 'body': latest.body, 'urgent': latest.urgent},
    })
