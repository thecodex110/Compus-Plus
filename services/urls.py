from django.urls import path

from . import views

app_name = 'services'

urlpatterns = [
    path('new/', views.new_request, name='new'),
    path('mine/', views.my_requests, name='mine'),
    path('queue/', views.queue, name='queue'),
    path('jobs/', views.my_jobs, name='jobs'),
    path('history/', views.history, name='history'),
    path('poll/', views.poll, name='poll'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/advance/', views.advance, name='advance'),
]
