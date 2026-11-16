from django.http import JsonResponse

from . import services
from .helpers import to_int
from .models import Address, Order
from .views import lines_of_order


def api_slots(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Нужно войти в аккаунт'}, status=401)
    address = Address.objects.filter(pk=to_int(request.GET.get('address')), user=request.user).first()
    if not address:
        return JsonResponse({'slots': []})
    slots = address.district.slots.all()
    return JsonResponse({'slots': [{'id': slot.pk, 'label': str(slot)} for slot in slots]})


def api_calc(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Нужно войти в аккаунт'}, status=401)
    returned = to_int(request.GET.get('returned'))
    order_pk = to_int(request.GET.get('order'), None)
    if order_pk:
        order = Order.objects.filter(pk=order_pk).first()
        if not order:
            return JsonResponse({'error': 'Заказ не найден'}, status=404)
        if order.user_id != request.user.id:
            return JsonResponse({'error': 'Нет доступа'}, status=403)
        lines = lines_of_order(order)
    else:
        lines = services.cart_lines(request)
    totals = services.calculate_order(lines, returned)
    return JsonResponse({
        'goods': str(totals['goods']),
        'deposit': str(totals['deposit']),
        'total': str(totals['total']),
        'missing': totals['missing'],
        'bottles': totals['bottles'],
    })
