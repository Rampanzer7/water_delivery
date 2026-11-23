import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, ProtectedError, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import (CoolerForm, DeliverySlotForm, DistrictForm, ProductForm,
                    SiteSettingForm, UserEditForm)
from .helpers import paginate, safe_next, to_int
from .models import (ContainerBalance, Cooler, DeliverySlot, District, Order,
                     OrderItem, Product, Rental, RouteSheet, SanitationRequest,
                     SiteSetting)
from .permissions import (DISPATCHER_GROUP, DRIVER_GROUP, is_admin,
                          is_dispatcher, is_driver, is_staff_member,
                          role_required)

User = get_user_model()

STAFF_SORTS = [
    ('-delivery_date', 'Дата доставки: сначала поздние'),
    ('delivery_date', 'Дата доставки: сначала ранние'),
    ('-total', 'Сумма по убыванию'),
    ('total', 'Сумма по возрастанию'),
    ('status', 'Статус А–Я'),
    ('-status', 'Статус Я–А'),
]


# ==============================================================================
# ОПЕРАТОР / ДИСПЕТЧЕРСКАЯ
# ==============================================================================

@role_required(is_dispatcher)
def operator_orders(request):
    orders = Order.objects.select_related('user__profile', 'address__district', 'slot', 'route_sheet__driver')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    district = to_int(request.GET.get('district'), None)
    date = request.GET.get('date', '')
    sort = request.GET.get('sort', '-delivery_date')

    if query:
        condition = Q(user__username__icontains=query) | Q(user__profile__phone__icontains=query)
        if query.isdigit():
            condition |= Q(pk=int(query))
        orders = orders.filter(condition)
    if status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)
    if district:
        orders = orders.filter(address__district_id=district)
    if date:
        orders = orders.filter(delivery_date=date)
    if sort not in dict(STAFF_SORTS):
        sort = '-delivery_date'

    page = paginate(request, orders.order_by(sort, 'pk'))
    return render(request, 'app/operator_orders.html', {
        'page': page,
        'query': query,
        'status': status,
        'district': district,
        'date': date,
        'sort': sort,
        'statuses': Order.STATUS_CHOICES,
        'districts': District.objects.all(),
        'sort_options': STAFF_SORTS,
        'drivers': User.objects.filter(groups__name=DRIVER_GROUP),
    })


staff_orders = operator_orders


@role_required(is_dispatcher)
def operator_order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('user__profile', 'address__district', 'slot', 'route_sheet__driver'), pk=pk)
    drivers = User.objects.filter(groups__name=DRIVER_GROUP)
    return render(request, 'app/operator_order_detail.html', {
        'order': order,
        'items': order.items.select_related('product'),
        'drivers': drivers,
    })


@role_required(is_dispatcher)
@require_POST
def staff_assign(request, pk):
    order = get_object_or_404(Order, pk=pk)
    driver = User.objects.filter(pk=to_int(request.POST.get('driver')), groups__name=DRIVER_GROUP).first()
    if not driver:
        messages.error(request, 'Выберите водителя.')
    elif not order.is_new:
        messages.error(request, 'Этот заказ уже передан водителю.')
    else:
        services.assign_order(order, driver)
        services.notify(order.user, f'Заказ №{order.pk} передан курьеру',
                        f'Курьер приедет {order.delivery_date:%d.%m.%Y} в интервале {order.slot}.')
        messages.success(request, f'Заказ №{order.pk} добавлен в маршрут водителя {driver.username}.')
    return redirect(safe_next(request, 'operator_orders'))


@role_required(is_dispatcher)
def operator_rentals(request):
    rentals = Rental.objects.select_related('user__profile', 'cooler', 'address__district').order_by('-start_date')
    status = request.GET.get('status', '')
    if status in dict(Rental.STATUS_CHOICES):
        rentals = rentals.filter(status=status)
    page = paginate(request, rentals)
    return render(request, 'app/operator_rentals.html', {
        'page': page,
        'status': status,
        'statuses': Rental.STATUS_CHOICES,
    })


@role_required(is_dispatcher)
def operator_rental_detail(request, pk):
    rental = get_object_or_404(Rental.objects.select_related('user__profile', 'cooler', 'address__district'), pk=pk)
    sanitations = rental.sanitations.all().order_by('-created_at')
    return render(request, 'app/operator_rental_detail.html', {
        'rental': rental,
        'sanitations': sanitations,
        'statuses': Rental.STATUS_CHOICES,
    })


@role_required(is_dispatcher)
@require_POST
def operator_rental_status(request, pk):
    rental = get_object_or_404(Rental, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Rental.STATUS_CHOICES):
        rental.status = new_status
        rental.save(update_fields=['status'])
        messages.success(request, f'Статус договора №{rental.pk} изменен на «{rental.get_status_display()}».')
    return redirect('operator_rental_detail', pk=rental.pk)


@role_required(is_dispatcher)
def operator_service(request):
    requests = SanitationRequest.objects.select_related('rental__cooler', 'rental__user__profile', 'rental__address').order_by('-created_at')
    status = request.GET.get('status', '')
    if status in dict(SanitationRequest.STATUS_CHOICES):
        requests = requests.filter(status=status)
    page = paginate(request, requests)
    return render(request, 'app/operator_service.html', {
        'page': page,
        'status': status,
        'statuses': SanitationRequest.STATUS_CHOICES,
    })


@role_required(is_dispatcher)
def operator_service_detail(request, pk):
    item = get_object_or_404(SanitationRequest.objects.select_related('rental__cooler', 'rental__user__profile', 'rental__address'), pk=pk)
    return render(request, 'app/operator_service_detail.html', {
        'req': item,
        'statuses': SanitationRequest.STATUS_CHOICES,
    })


@role_required(is_dispatcher)
@require_POST
def operator_service_status(request, pk):
    item = get_object_or_404(SanitationRequest, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(SanitationRequest.STATUS_CHOICES):
        item.status = new_status
        item.save(update_fields=['status'])
        messages.success(request, f'Статус заявки №{item.pk} изменен на «{item.get_status_display()}».')
    return redirect('operator_service_detail', pk=item.pk)


@role_required(is_dispatcher)
def stats(request):
    orders = Order.objects.all()
    totals = orders.aggregate(
        count=Count('id'),
        revenue=Sum('total'),
        average=Avg('total'),
        delivered=Count('id', filter=Q(status=Order.DELIVERED)),
        deposit=Sum('deposit_total'),
    )
    bottles = orders.filter(status=Order.DELIVERED).aggregate(total=Sum('bottles_total'))['total'] or 0
    share = round(totals['delivered'] * 100 / totals['count'], 1) if totals['count'] else 0
    active_rentals = Rental.objects.filter(status=Rental.ACTIVE).count()

    since = timezone.localdate() - timedelta(days=13)
    by_day = orders.filter(delivery_date__gte=since).values('delivery_date').annotate(n=Count('id')).order_by('delivery_date')
    by_district = orders.values('address__district__name').annotate(n=Count('id')).order_by('-n')

    return render(request, 'app/stats.html', {
        'count': totals['count'],
        'revenue': totals['revenue'] or 0,
        'average': round(totals['average'] or 0, 2),
        'deposit': totals['deposit'] or 0,
        'share': share,
        'bottles': bottles,
        'active_rentals': active_rentals,
        'day_labels': [row['delivery_date'].strftime('%d.%m') for row in by_day],
        'day_values': [row['n'] for row in by_day],
        'district_labels': [row['address__district__name'] for row in by_district],
        'district_values': [row['n'] for row in by_district],
    })


# ==============================================================================
# КУРЬЕР / ВОДИТЕЛЬ
# ==============================================================================

@role_required(is_staff_member)
def routes(request):
    sheets = RouteSheet.objects.select_related('driver')
    if not is_dispatcher(request.user):
        sheets = sheets.filter(driver=request.user)
    sheets = sheets.annotate(orders_count=Count('orders'), orders_sum=Sum('orders__total')).order_by('-date')
    return render(request, 'app/routes.html', {'page': paginate(request, sheets)})


def get_sheet_for(user, pk):
    sheet = get_object_or_404(RouteSheet.objects.select_related('driver'), pk=pk)
    if sheet.driver_id != user.id and not is_dispatcher(user):
        raise PermissionDenied
    return sheet


@role_required(is_staff_member)
def route_detail(request, pk):
    sheet = get_sheet_for(request.user, pk)
    orders = sheet.orders.select_related('user', 'address__district', 'slot').order_by('slot__start')
    return render(request, 'app/route_detail.html', {'sheet': sheet, 'orders': orders})


@role_required(is_staff_member)
def route_csv(request, pk):
    sheet = get_sheet_for(request.user, pk)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="route_{sheet.pk}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Заказ', 'Интервал', 'Адрес', 'Клиент', 'Телефон', 'Бутылей', 'Сдаёт пустых', 'К оплате', 'Статус'])
    orders = sheet.orders.select_related('user__profile', 'address__district', 'slot').order_by('slot__start')
    for order in orders:
        profile = getattr(order.user, 'profile', None)
        phone = profile.phone if profile else ''
        writer.writerow([
            order.pk, order.slot, order.address, order.user.username, phone,
            order.bottles_total, order.returned_bottles, order.total, order.get_status_display(),
        ])
    return response


@role_required(is_staff_member)
def courier_deliveries(request):
    orders = Order.objects.filter(
        route_sheet__driver=request.user,
        status=Order.ASSIGNED
    ).select_related('user__profile', 'address__district', 'slot').order_by('slot__start')
    return render(request, 'app/courier_deliveries.html', {
        'orders': orders,
        'today': timezone.localdate(),
    })


@role_required(is_staff_member)
def courier_delivery_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('user__profile', 'address__district', 'slot', 'route_sheet'), pk=pk)
    if order.route_sheet and order.route_sheet.driver_id != request.user.id and not is_dispatcher(request.user):
        raise PermissionDenied
    balance_obj = ContainerBalance.objects.filter(user=order.user).first()
    current_balance = balance_obj.bottles if balance_obj else 0
    return render(request, 'app/courier_delivery_detail.html', {
        'order': order,
        'items': order.items.select_related('product'),
        'current_balance': current_balance,
    })


@role_required(is_staff_member)
def courier_close_delivery(request, pk):
    order = get_object_or_404(Order.objects.select_related('user', 'route_sheet'), pk=pk)
    if order.route_sheet and order.route_sheet.driver_id != request.user.id and not is_dispatcher(request.user):
        raise PermissionDenied

    balance_obj = ContainerBalance.objects.filter(user=order.user).first()
    current_balance = balance_obj.bottles if balance_obj else 0

    if request.method == 'POST':
        if order.status != Order.ASSIGNED:
            messages.error(request, 'Закрыть можно только заказ в статусе «В пути / Назначен».')
            return redirect('courier_delivery_detail', pk=order.pk)

        returned_bottles = to_int(request.POST.get('returned_bottles'), 0)
        if returned_bottles > current_balance:
            messages.error(
                request,
                f'Количество сдаваемых бутылей ({returned_bottles}) не может превышать количество бутылей у клиента на руках ({current_balance}).'
            )
            return redirect('courier_delivery_detail', pk=order.pk)

        try:
            closed = services.close_delivery(order.pk, returned_bottles=returned_bottles)
        except services.ServiceError as error:
            messages.error(request, str(error))
            return redirect('courier_delivery_detail', pk=order.pk)

        messages.success(request, f'Доставка заказа №{closed.pk} успешно завершена! Баланс тары клиента обновлен.')
        return redirect('courier_deliveries')

    return redirect('courier_delivery_detail', pk=order.pk)


@role_required(is_staff_member)
def close_delivery(request, pk):
    order = get_object_or_404(Order.objects.select_related('route_sheet', 'user', 'address__district', 'slot'), pk=pk)
    if not order.route_sheet_id and not request.user.is_superuser and not is_dispatcher(request.user):
        raise PermissionDenied
    sheet = get_sheet_for(request.user, order.route_sheet_id) if order.route_sheet_id else None

    balance_obj = getattr(order.user, 'container_balance', None)
    current_balance = balance_obj.bottles if balance_obj else 0

    if request.method == 'POST':
        delivered_bottles = to_int(request.POST.get('delivered_bottles'), order.bottles_total)
        returned_bottles = to_int(request.POST.get('returned_bottles'), order.returned_bottles)
        if returned_bottles > current_balance:
            messages.error(
                request,
                f'Количество сдаваемых бутылей ({returned_bottles}) не может превышать количество бутылей у клиента на руках ({current_balance}).'
            )
            return redirect('close_delivery', pk=order.pk)

        order.bottles_total = delivered_bottles
        order.returned_bottles = returned_bottles
        order.save(update_fields=['bottles_total', 'returned_bottles'])

        try:
            closed = services.close_delivery(order.pk, returned_bottles=returned_bottles)
        except services.ServiceError as error:
            messages.error(request, str(error))
            return redirect('close_delivery', pk=order.pk)
        else:
            services.notify(closed.user, f'Заказ №{closed.pk} доставлен',
                            f'Спасибо! Бутылей на руках теперь: {closed.user.container_balance.bottles}.')
            messages.success(request, f'Доставка заказа №{closed.pk} закрыта, баланс тары обновлён.')
            if sheet:
                return redirect('route_detail', pk=sheet.pk)
            return redirect('operator_orders')

    post_close_balance = max(current_balance + order.bottles_total - order.returned_bottles, 0)
    post_close_deposit = post_close_balance * 300

    return render(request, 'app/close_delivery.html', {
        'order': order,
        'current_balance': current_balance,
        'post_close_balance': post_close_balance,
        'post_close_deposit': post_close_deposit,
        'sheet': sheet,
    })


# ==============================================================================
# АДМИНИСТРАТОР
# ==============================================================================

@role_required(is_admin)
def manage_dashboard(request):
    return redirect('manage_settings')


@role_required(is_admin)
def manage_settings(request):
    s_discount = SiteSetting.objects.filter(key='first_order_discount').first()
    s_min_bottles = SiteSetting.objects.filter(key='min_order_bottles').first()
    s_note = SiteSetting.objects.filter(key='delivery_note').first()

    initial = {
        'first_order_discount': int(s_discount.value) if s_discount and s_discount.value.isdigit() else 10,
        'min_order_bottles': int(s_min_bottles.value) if s_min_bottles and s_min_bottles.value.isdigit() else 2,
        'delivery_note': s_note.value if s_note else 'Бесплатная доставка от 2 бутылей воды 19 л во все районы города.',
    }

    form = SiteSettingForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        SiteSetting.objects.update_or_create(
            key='first_order_discount',
            defaults={'value': str(form.cleaned_data['first_order_discount']), 'description': 'Скидка на первый заказ (%)'}
        )
        SiteSetting.objects.update_or_create(
            key='min_order_bottles',
            defaults={'value': str(form.cleaned_data['min_order_bottles']), 'description': 'Минимальный объем заказа (бутылей)'}
        )
        SiteSetting.objects.update_or_create(
            key='delivery_note',
            defaults={'value': form.cleaned_data['delivery_note'], 'description': 'Условия доставки'}
        )
        messages.success(request, 'Настройки системы успешно сохранены.')
        return redirect('manage_settings')

    return render(request, 'app/manage_settings.html', {'form': form})


@role_required(is_admin)
def manage_users(request):
    users = User.objects.select_related('profile').prefetch_related('groups').order_by('-date_joined')
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')

    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query) | Q(profile__phone__icontains=query))
    if role == 'admin':
        users = users.filter(Q(is_superuser=True) | Q(is_staff=True))
    elif role == 'dispatcher':
        users = users.filter(groups__name=DISPATCHER_GROUP)
    elif role == 'driver':
        users = users.filter(groups__name=DRIVER_GROUP)
    elif role == 'client':
        users = users.filter(is_superuser=False, is_staff=False).exclude(groups__name__in=[DISPATCHER_GROUP, DRIVER_GROUP])

    page = paginate(request, users)
    return render(request, 'app/manage_users.html', {
        'page': page,
        'query': query,
        'role': role,
    })


@role_required(is_admin)
def manage_user_edit(request, pk):
    target_user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    form = UserEditForm(request.POST or None, instance=target_user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        phone = form.cleaned_data.get('phone', '')
        if hasattr(user, 'profile'):
            user.profile.phone = phone
            user.profile.save(update_fields=['phone'])
        else:
            from .models import Profile
            Profile.objects.create(user=user, phone=phone)

        role = form.cleaned_data.get('role')
        dispatcher_group, _ = Group.objects.get_or_create(name=DISPATCHER_GROUP)
        driver_group, _ = Group.objects.get_or_create(name=DRIVER_GROUP)

        if role == 'admin':
            user.is_staff = True
            user.is_superuser = True
            user.groups.remove(dispatcher_group, driver_group)
        elif role == 'dispatcher':
            user.is_staff = True
            user.is_superuser = False
            user.groups.add(dispatcher_group)
            user.groups.remove(driver_group)
        elif role == 'driver':
            user.is_staff = False
            user.is_superuser = False
            user.groups.add(driver_group)
            user.groups.remove(dispatcher_group)
        else:  # client
            user.is_staff = False
            user.is_superuser = False
            user.groups.remove(dispatcher_group, driver_group)

        user.save()
        messages.success(request, f'Данные пользователя {user.username} обновлены.')
        return redirect('manage_users')

    return render(request, 'app/manage_user_edit.html', {'form': form, 'target_user': target_user})


@role_required(is_admin)
def manage_intervals(request):
    slots = DeliverySlot.objects.prefetch_related('districts').order_by('start')
    return render(request, 'app/manage_intervals.html', {'slots': slots})


@role_required(is_admin)
def manage_interval_create(request):
    form = DeliverySlotForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Интервал доставки добавлен.')
        return redirect('manage_intervals')
    return render(request, 'app/manage_interval_form.html', {'form': form, 'title': 'Новый интервал доставки'})


@role_required(is_admin)
def manage_interval_edit(request, pk):
    slot = get_object_or_404(DeliverySlot, pk=pk)
    form = DeliverySlotForm(request.POST or None, instance=slot)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Интервал доставки сохранен.')
        return redirect('manage_intervals')
    return render(request, 'app/manage_interval_form.html', {'form': form, 'title': 'Редактировать интервал доставки', 'slot': slot})


@role_required(is_admin)
def manage_interval_delete(request, pk):
    slot = get_object_or_404(DeliverySlot, pk=pk)
    if request.method == 'POST':
        try:
            slot.delete()
            messages.success(request, 'Интервал доставки удален.')
        except ProtectedError:
            messages.error(request, 'Интервал используется в заказах, его нельзя удалить.')
        return redirect('manage_intervals')
    return render(request, 'app/confirm_delete.html', {
        'title': f'Удалить интервал {slot}?',
        'back': 'manage_intervals',
    })


@role_required(is_admin)
def manage_districts(request):
    districts = District.objects.annotate(orders_count=Count('address__order')).order_by('name')
    return render(request, 'app/manage_districts.html', {'districts': districts})


@role_required(is_admin)
def manage_district_create(request):
    form = DistrictForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Район добавлен.')
        return redirect('manage_districts')
    return render(request, 'app/manage_district_form.html', {'form': form, 'title': 'Новый район'})


@role_required(is_admin)
def manage_district_edit(request, pk):
    district = get_object_or_404(District, pk=pk)
    form = DistrictForm(request.POST or None, instance=district)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Район сохранен.')
        return redirect('manage_districts')
    return render(request, 'app/manage_district_form.html', {'form': form, 'title': 'Редактировать район', 'district': district})


@role_required(is_admin)
def manage_district_delete(request, pk):
    district = get_object_or_404(District, pk=pk)
    if request.method == 'POST':
        try:
            district.delete()
            messages.success(request, 'Район удален.')
        except ProtectedError:
            messages.error(request, 'Район используется в адресах пользователей, его нельзя удалить.')
        return redirect('manage_districts')
    return render(request, 'app/confirm_delete.html', {
        'title': f'Удалить район {district.name}?',
        'back': 'manage_districts',
    })


@role_required(is_admin)
def manage_coolers(request):
    coolers = Cooler.objects.all().order_by('pk')
    return render(request, 'app/manage_coolers.html', {'coolers': coolers})


@role_required(is_admin)
def manage_cooler_create(request):
    form = CoolerForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        cooler = form.save()
        Product.objects.get_or_create(
            name=cooler.name,
            kind=Product.COOLER,
            defaults={
                'price': cooler.monthly_price,
                'deposit_price': cooler.deposit,
                'stock': cooler.quantity,
                'description': cooler.description,
                'photo': cooler.photo,
                'is_active': True,
            }
        )
        messages.success(request, f'Кулер «{cooler.name}» успешно добавлен.')
        return redirect('manage_coolers')
    return render(request, 'app/manage_cooler_form.html', {'form': form, 'title': 'Добавить кулер в парк'})


@role_required(is_admin)
def manage_cooler_edit(request, pk):
    cooler = get_object_or_404(Cooler, pk=pk)
    form = CoolerForm(request.POST or None, request.FILES or None, instance=cooler)
    if request.method == 'POST' and form.is_valid():
        cooler = form.save()
        Product.objects.filter(name=cooler.name, kind=Product.COOLER).update(
            price=cooler.monthly_price,
            deposit_price=cooler.deposit,
            stock=cooler.quantity,
            description=cooler.description,
        )
        messages.success(request, f'Кулер «{cooler.name}» обновлен.')
        return redirect('manage_coolers')
    return render(request, 'app/manage_cooler_form.html', {'form': form, 'title': f'Редактировать кулер «{cooler.name}»', 'cooler': cooler})


@role_required(is_admin)
def manage_cooler_delete(request, pk):
    cooler = get_object_or_404(Cooler, pk=pk)
    if request.method == 'POST':
        if cooler.rentals.filter(status=Rental.ACTIVE).exists():
            messages.error(request, 'Кулер находится в активной аренде, удалить его невозможно.')
        else:
            cooler.delete()
            Product.objects.filter(name=cooler.name, kind=Product.COOLER).delete()
            messages.success(request, f'Кулер «{cooler.name}» удален.')
        return redirect('manage_coolers')
    return render(request, 'app/confirm_delete.html', {
        'title': f'Удалить кулер «{cooler.name}»?',
        'back': 'manage_coolers',
    })


@role_required(is_admin)
def manage_products(request):
    products = Product.objects.all().order_by('-pk')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    kind = request.GET.get('kind', '')

    if query:
        products = products.filter(name__icontains=query)
    if status == 'active':
        products = products.filter(is_active=True)
    elif status == 'inactive':
        products = products.filter(is_active=False)
    if kind:
        products = products.filter(kind=kind)

    page = paginate(request, products)
    return render(request, 'app/manage_products.html', {
        'page': page,
        'query': query,
        'status': status,
        'kind': kind,
    })


@role_required(is_admin)
def manage_product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Товар «{product.name}» успешно добавлен и опубликован.')
        return redirect('manage_products')
    return render(request, 'app/manage_product_form.html', {'form': form, 'title': 'Добавить новый товар'})


@role_required(is_admin)
def manage_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Товар «{product.name}» успешно сохранен.')
        return redirect('manage_products')
    return render(request, 'app/manage_product_form.html', {'form': form, 'title': f'Редактировать «{product.name}»', 'product': product})


@role_required(is_admin)
def manage_product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        has_orders = OrderItem.objects.filter(product=product).exists()
        if has_orders:
            product.is_active = False
            product.save(update_fields=['is_active'])
            messages.warning(
                request,
                f'Товар «{product.name}» скрыт из каталога, так как по нему есть история заказов. Удаление невозможно для сохранения истории.'
            )
        else:
            product.delete()
            messages.success(request, f'Товар «{product.name}» успешно удален.')
        return redirect('manage_products')
    return render(request, 'app/confirm_delete.html', {
        'title': f'Удалить товар «{product.name}»?',
        'back': 'manage_products',
    })
