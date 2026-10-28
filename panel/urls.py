from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.users, name='users'),
    path('users/new/', views.create_user, name='create_user'),
    path('users/<int:pk>/toggle/', views.toggle_active, name='toggle_active'),
    path('campus/', views.locations, name='locations'),
    path('campus/<int:pk>/delete/', views.delete_location, name='delete_location'),
    path('hospitals/', views.hospitals, name='hospitals'),
    path('hospitals/new/', views.hospital_form, name='hospital_new'),
    path('hospitals/<int:pk>/', views.hospital_form, name='hospital_edit'),
    path('hospitals/<int:pk>/delete/', views.delete_hospital, name='hospital_delete'),
    path('moderate/', views.moderate, name='moderate'),
    path('moderate/<str:kind>/<int:pk>/remove/', views.remove_item, name='remove_item'),
]
