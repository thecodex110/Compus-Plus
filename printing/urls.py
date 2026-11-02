from django.urls import path

from . import views

app_name = 'printing'

urlpatterns = [
    path('', views.shops, name='shops'),
    path('shop/<int:shop_id>/new/', views.new_order, name='new'),
    path('orders/', views.my_orders, name='mine'),
    path('orders/<int:pk>/', views.order_detail, name='order'),
    path('orders/<int:pk>/options/', views.edit_options, name='edit_options'),
    path('orders/<int:pk>/pay/', views.pay, name='pay'),
    path('orders/<int:pk>/discard/', views.cancel_draft, name='discard'),
    path('orders/<int:pk>/<str:kind>/', views.download, name='download'),
    path('poll/', views.poll, name='poll'),

    path('shop/', views.shop_dashboard, name='shop_dashboard'),
    path('shop/orders/<int:pk>/', views.shop_order, name='shop_order'),
    path('shop/orders/<int:pk>/advance/', views.shop_advance, name='shop_advance'),
    path('shop/orders/<int:pk>/reject/', views.shop_reject, name='shop_reject'),
    path('shop/toggle/', views.toggle_open, name='toggle_open'),
    path('shop/settings/', views.shop_settings, name='shop_settings'),
    path('shop/stationery/', views.shop_stationery, name='shop_stationery'),
    path('shop/stationery/<int:pk>/', views.stationery_update, name='stationery_update'),
]
