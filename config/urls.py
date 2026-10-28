from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts import views as account_views

admin.site.site_header = 'COEP Campus Portal — Admin'

urlpatterns = [
    path('', account_views.home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('services/', include('services.urls')),
    path('lost-found/', include('lostfound.urls')),
    path('print/', include('printing.urls')),
    path('market/', include('market.urls')),
    path('django-admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
