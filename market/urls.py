from django.urls import path

from . import views

app_name = 'market'

urlpatterns = [
    path('', views.browse, name='browse'),
    path('sell/', views.sell, name='sell'),
    path('mine/', views.mine, name='mine'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/edit/', views.edit, name='edit'),
    path('<int:pk>/sold/', views.mark_sold, name='sold'),
    path('<int:pk>/delete/', views.delete, name='delete'),
    path('<int:pk>/remove/', views.remove, name='remove'),
]
