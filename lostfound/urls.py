from django.urls import path

from . import views

app_name = 'lostfound'

urlpatterns = [
    path('', views.feed, name='feed'),
    path('new/', views.new_post, name='new'),
    path('mine/', views.my_posts, name='mine'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/returned/', views.mark_returned, name='returned'),
    path('<int:pk>/remove/', views.remove, name='remove'),
]
