from django.urls import path

from . import views

app_name = 'notify'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('poll/', views.poll, name='poll'),
    path('read-all/', views.mark_all_read, name='read_all'),
    path('<int:pk>/', views.open_one, name='open'),
]
