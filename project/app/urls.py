from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import api, staff_views, views

urlpatterns = [
    # Публичные страницы
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/', views.product_detail),
    path('search/', views.catalog, name='search'),
    path('coolers/', views.coolers, name='coolers'),
    path('coolers/<int:pk>/', views.cooler_detail, name='cooler_detail'),
    path('coolers/<int:pk>/rent/', views.rent_cooler, name='rent_cooler'),
    path('conditions/', views.conditions, name='conditions'),

    # Корзина и заказ
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/new/', views.order_new, name='order_new'),
    path('order/<int:pk>/done/', views.order_done, name='order_done'),

    # Авторизация и регистрация (с защитой от перебора паролей SEC-01)
    path('accounts/login/', views.RateLimitedLoginView.as_view(), name='login'),
    path('accounts/register/', views.register, name='register'),
    path('accounts/password/', auth_views.PasswordChangeView.as_view(success_url=reverse_lazy('password_change_done')), name='password_change'),
    path('accounts/password/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('login/', views.RateLimitedLoginView.as_view()),
    path('register/', views.register),
    path('password/', auth_views.PasswordChangeView.as_view(success_url=reverse_lazy('password_change_done'))),
    path('password/done/', auth_views.PasswordChangeDoneView.as_view()),
    path('logout/', auth_views.LogoutView.as_view()),

    # Личный кабинет клиента
    path('cabinet/', views.cabinet, name='cabinet'),
    path('profile/', views.profile, name='profile'),
    path('cabinet/balance/', views.cabinet_balance, name='cabinet_balance'),
    path('cabinet/schedules/', views.cabinet_schedules, name='cabinet_schedules'),
    path('cabinet/schedules/new/', views.cabinet_schedule_create, name='cabinet_schedule_create'),
    path('cabinet/schedules/<int:pk>/toggle/', views.cabinet_schedule_toggle, name='cabinet_schedule_toggle'),
    path('cabinet/schedules/<int:pk>/delete/', views.cabinet_schedule_delete, name='cabinet_schedule_delete'),

    path('cabinet/rentals/', views.my_rentals, name='cabinet_rentals'),
    path('rentals/', views.my_rentals, name='my_rentals'),
    path('cabinet/rentals/<int:pk>/', views.cabinet_rental_detail, name='cabinet_rental_detail'),
    path('cabinet/rentals/<int:pk>/service/', views.sanitation, name='cabinet_rental_service'),
    path('cabinet/rentals/<int:pk>/service/', views.sanitation, name='cabinet_sanitation'),
    path('rentals/<int:pk>/sanitation/', views.sanitation, name='sanitation'),

    path('cabinet/orders/', views.my_orders, name='cabinet_orders'),
    path('orders/', views.my_orders, name='my_orders'),
    path('cabinet/orders/<int:pk>/', views.order_detail, name='cabinet_order_detail'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('cabinet/orders/<int:pk>/edit/', views.order_edit, name='cabinet_order_edit'),
    path('orders/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('cabinet/orders/<int:pk>/delete/', views.order_delete, name='cabinet_order_delete'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),

    path('cabinet/addresses/', views.address_list, name='cabinet_addresses'),
    path('addresses/', views.address_list, name='address_list'),
    path('cabinet/addresses/new/', views.address_create, name='cabinet_address_create'),
    path('addresses/new/', views.address_create, name='address_create'),
    path('cabinet/addresses/<int:pk>/edit/', views.address_edit, name='cabinet_address_edit'),
    path('addresses/<int:pk>/edit/', views.address_edit, name='address_edit'),
    path('cabinet/addresses/<int:pk>/delete/', views.address_delete, name='cabinet_address_delete'),
    path('addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),
    path('addresses/<int:pk>/delete/', views.address_delete),

    # Рабочее место оператора
    path('operator/orders/', staff_views.operator_orders, name='operator_orders'),
    path('staff/orders/', staff_views.operator_orders, name='staff_orders'),
    path('operator/orders/<int:pk>/', staff_views.operator_order_detail, name='operator_order_detail'),
    path('operator/orders/<int:pk>/assign/', staff_views.staff_assign, name='operator_order_assign'),
    path('staff/orders/<int:pk>/assign/', staff_views.staff_assign, name='staff_assign'),
    path('operator/rentals/', staff_views.operator_rentals, name='operator_rentals'),
    path('operator/rentals/<int:pk>/', staff_views.operator_rental_detail, name='operator_rental_detail'),
    path('operator/rentals/<int:pk>/status/', staff_views.operator_rental_status, name='operator_rental_status'),
    path('operator/service/', staff_views.operator_service, name='operator_service'),
    path('operator/service/<int:pk>/', staff_views.operator_service_detail, name='operator_service_detail'),
    path('operator/service/<int:pk>/status/', staff_views.operator_service_status, name='operator_service_status'),
    path('staff/stats/', staff_views.stats, name='stats'),
    path('manage/stats/', staff_views.stats, name='manage_stats'),
    path('routes/', staff_views.routes, name='routes'),
    path('staff/routes/', staff_views.routes, name='staff_routes'),
    path('routes/<int:pk>/', staff_views.route_detail, name='route_detail'),
    path('staff/routes/<int:pk>/', staff_views.route_detail, name='staff_route_detail'),
    path('routes/<int:pk>/csv/', staff_views.route_csv, name='route_csv'),
    path('staff/routes/<int:pk>/csv/', staff_views.route_csv, name='staff_route_csv'),
    path('deliveries/<int:pk>/close/', staff_views.close_delivery, name='close_delivery'),

    # Рабочее место курьера
    path('courier/', staff_views.courier_deliveries, name='courier_deliveries'),
    path('courier/deliveries/', staff_views.courier_deliveries),
    path('courier/deliveries/<int:pk>/', staff_views.courier_delivery_detail, name='courier_delivery_detail'),
    path('courier/deliveries/<int:pk>/close/', staff_views.courier_close_delivery, name='courier_close_delivery'),
    path('courier/deliveries/<int:pk>/finish/', staff_views.courier_close_delivery, name='courier_delivery_close'),

    # Панель администратора
    path('manage/', staff_views.manage_dashboard, name='manage_dashboard'),
    path('manage/settings/', staff_views.manage_settings, name='manage_settings'),
    path('manage/users/', staff_views.manage_users, name='manage_users'),
    path('manage/users/<int:pk>/edit/', staff_views.manage_user_edit, name='manage_user_edit'),
    path('manage/intervals/', staff_views.manage_intervals, name='manage_intervals'),
    path('manage/intervals/new/', staff_views.manage_interval_create, name='manage_interval_create'),
    path('manage/intervals/<int:pk>/edit/', staff_views.manage_interval_edit, name='manage_interval_edit'),
    path('manage/intervals/<int:pk>/delete/', staff_views.manage_interval_delete, name='manage_interval_delete'),
    path('manage/districts/', staff_views.manage_districts, name='manage_districts'),
    path('manage/districts/new/', staff_views.manage_district_create, name='manage_district_create'),
    path('manage/districts/<int:pk>/edit/', staff_views.manage_district_edit, name='manage_district_edit'),
    path('manage/districts/<int:pk>/delete/', staff_views.manage_district_delete, name='manage_district_delete'),
    path('manage/coolers/', staff_views.manage_coolers, name='manage_coolers'),
    path('manage/coolers/new/', staff_views.manage_cooler_create, name='manage_cooler_create'),
    path('manage/coolers/<int:pk>/edit/', staff_views.manage_cooler_edit, name='manage_cooler_edit'),
    path('manage/coolers/<int:pk>/delete/', staff_views.manage_cooler_delete, name='manage_cooler_delete'),
    path('manage/products/', staff_views.manage_products, name='manage_products'),
    path('manage/products/new/', staff_views.manage_product_create, name='manage_product_create'),
    path('manage/products/<int:pk>/edit/', staff_views.manage_product_edit, name='manage_product_edit'),
    path('manage/products/<int:pk>/delete/', staff_views.manage_product_delete, name='manage_product_delete'),

    # Страницы ошибок (для проверки)
    path('403/', views.custom_403, name='custom_403'),
    path('404/', views.custom_404, name='custom_404'),
    path('500/', views.custom_500, name='custom_500'),

    # API
    path('api/slots/', api.api_slots, name='api_slots'),
    path('api/calc/', api.api_calc, name='api_calc'),
    path('api/search/', api.api_search, name='api_search'),
    path('api/quickview/<int:pk>/', api.api_quickview, name='api_quickview'),
    path('defects/', views.defects_summary, name='defects_summary'),
]

