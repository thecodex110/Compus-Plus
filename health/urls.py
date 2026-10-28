from django.urls import path

from . import views

app_name = 'health'

urlpatterns = [
    path('', views.directory, name='directory'),
    path('me/', views.my_entry, name='me'),
    path('me/toggle/', views.toggle_visible, name='toggle'),
    path('me/delete/', views.delete_entry, name='delete'),
    path('donor/<int:pk>/reveal/', views.reveal, name='reveal'),
    path('hospitals/', views.hospitals, name='hospitals'),
]
