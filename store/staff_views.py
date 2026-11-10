import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .helpers import paginate, safe_next, to_int
from .models import District, Order, Rental, RouteSheet
from .permissions import DRIVER_GROUP, is_dispatcher, is_staff_member, role_required

User = get_user_model()

STAFF_SORTS = [
    ('-delivery_date', 'Дата доставки: сначала поздние'),
    ('delivery_date', 'Дата доставки: сначала ранние'),
    ('-total', 'Сумма по убыванию'),
    ('total', 'Сумма по возрастанию'),
    ('status', 'Статус А–Я'),
    ('-status', 'Статус Я–А'),
]


@role_required(is_dispatcher)
def staff_orders(request):
    orders = Order.objects.select_related('user', 'address__district', 'slot', 'route_sheet__driver')
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
    return render(request, 'store/staff_orders.html', {
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
    return redirect(safe_next(request, 'staff_orders'))


@role_required(is_staff_member)
def routes(request):
    sheets = RouteSheet.objects.select_related('driver')
    if not is_dispatcher(request.user):
        sheets = sheets.filter(driver=request.user)
    sheets = sheets.annotate(orders_count=Count('orders'), orders_sum=Sum('orders__total')).order_by('-date')
    return render(request, 'store/routes.html', {'page': paginate(request, sheets)})


def get_sheet_for(user, pk):
    sheet = get_object_or_404(RouteSheet.objects.select_related('driver'), pk=pk)
    if sheet.driver_id != user.id and not is_dispatcher(user):
        raise PermissionDenied
    return sheet


@role_required(is_staff_member)
def route_detail(request, pk):
    sheet = get_sheet_for(request.user, pk)
    orders = sheet.orders.select_related('user', 'address__district', 'slot').order_by('slot__start')
    return render(request, 'store/route_detail.html', {'sheet': sheet, 'orders': orders})


@role_required(is_staff_member)
def route_csv(request, pk):
    sheet = get_sheet_for(request.user, pk)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="route_{sheet.pk}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Заказ', 'Интервал', 'Адрес', 'Клиент', 'Телефон', 'Бутылей', 'Сдаёт пустых', 'К оплате', 'Статус'])
    for order in sheet.orders.select_related('user__profile', 'address__district', 'slot').order_by('slot__start'):
        phone = order.user.profile.phone if hasattr(order.user, 'profile') else ''
        writer.writerow([
            order.pk, order.slot, order.address, order.user.username, phone,
            order.bottles_total, order.returned_bottles, order.total, order.get_status_display(),
        ])
    return response


@role_required(is_staff_member)
@require_POST
def close_delivery(request, pk):
    order = get_object_or_404(Order.objects.select_related('route_sheet'), pk=pk)
    if not order.route_sheet_id:
        raise PermissionDenied
    sheet = get_sheet_for(request.user, order.route_sheet_id)
    try:
        closed = services.close_delivery(order.pk)
    except services.ServiceError as error:
        messages.error(request, str(error))
    else:
        services.notify(closed.user, f'Заказ №{closed.pk} доставлен',
                        f'Спасибо! Бутылей на руках теперь: {closed.user.container_balance.bottles}.')
        messages.success(request, f'Доставка заказа №{closed.pk} закрыта, баланс тары обновлён.')
    return redirect('route_detail', pk=sheet.pk)


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

    return render(request, 'store/stats.html', {
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
