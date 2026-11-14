from django.contrib import admin
from django.urls import include, path, re_path

from accounts import views as account_views

from . import views

admin.site.site_header = 'COEP Campus Portal — Admin'

urlpatterns = [
    path('', account_views.home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('services/', include('services.urls')),
    path('lost-found/', include('lostfound.urls')),
    path('print/', include('printing.urls')),
    path('market/', include('market.urls')),
    path('blood/', include('health.urls')),
    path('notifications/', include('notify.urls')),
    path('admin-panel/', include('panel.urls')),
    path('django-admin/', admin.site.urls),
    path('healthz/', views.healthz, name='healthz'),
    path('internal/purge-print-files/', views.purge_print_files, name='purge_print_files'),
    # Public uploads (photos, shop QR). Print files never pass through here.
    re_path(r'^media/(?P<path>.*)$', views.media),
]
