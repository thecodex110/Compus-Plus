import hmac
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.static import serve


def healthz(request):
    """Plain 200 for the host's health check: no database, no login, no HTTPS redirect."""
    return HttpResponse('ok', content_type='text/plain')


def media(request, path):
    """Public uploads (photos, shop QR). Print files and payment screenshots live in
    PRIVATE_MEDIA_ROOT and are only ever sent by the permission-checked download view."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


@csrf_exempt
def purge_print_files(request):
    """Daily clean-up trigger. A Render cron job cannot mount the web service's disk, so the
    clean-up runs here and the cron job only calls this URL with the shared token.
    Anyone without the token gets a plain 404, so the URL looks like it does not exist."""
    auth = request.headers.get('Authorization', '')
    given = auth[len('Bearer '):] if auth.startswith('Bearer ') else ''
    token = settings.CRON_TOKEN
    if request.method != 'POST' or not token or not hmac.compare_digest(given.encode(), token.encode()):
        raise Http404
    out = StringIO()
    call_command('purge_print_files', stdout=out)
    return JsonResponse({'ok': True, 'result': out.getvalue().strip()})
