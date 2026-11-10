from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import api, staff_views, views

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),

    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),

    path('addresses/', views.address_list, name='address_list'),
    path('addresses/new/', views.address_create, name='address_create'),
    path('addresses/<int:pk>/edit/', views.address_edit, name='address_edit'),
    path('addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),

    path('coolers/', views.coolers, name='coolers'),
    path('coolers/<int:pk>/rent/', views.rent_cooler, name='rent_cooler'),
    path('rentals/', views.my_rentals, name='my_rentals'),
    path('rentals/<int:pk>/sanitation/', views.sanitation, name='sanitation'),

    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password/', auth_views.PasswordChangeView.as_view(success_url=reverse_lazy('password_change_done')), name='password_change'),
    path('password/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('profile/', views.profile, name='profile'),

    path('staff/orders/', staff_views.staff_orders, name='staff_orders'),
    path('staff/orders/<int:pk>/assign/', staff_views.staff_assign, name='staff_assign'),
    path('staff/stats/', staff_views.stats, name='stats'),
    path('routes/', staff_views.routes, name='routes'),
    path('routes/<int:pk>/', staff_views.route_detail, name='route_detail'),
    path('routes/<int:pk>/csv/', staff_views.route_csv, name='route_csv'),
    path('deliveries/<int:pk>/close/', staff_views.close_delivery, name='close_delivery'),

    path('api/slots/', api.api_slots, name='api_slots'),
    path('api/calc/', api.api_calc, name='api_calc'),
]
