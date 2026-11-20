from django.http import JsonResponse
from django.urls import reverse

from . import services
from .helpers import to_int
from .models import Address, Cooler, Order, Product
from .views import lines_of_order


def api_slots(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Нужно войти в аккаунт'}, status=401)
    address = Address.objects.filter(pk=to_int(request.GET.get('address')), user=request.user).first()
    if not address:
        return JsonResponse({'slots': []})
    slots = address.district.slots.all()
    return JsonResponse(
        {'slots': [{'id': slot.pk, 'label': str(slot)} for slot in slots]},
        json_dumps_params={'ensure_ascii': False}
    )


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
    }, json_dumps_params={'ensure_ascii': False})


def api_search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'query': '', 'count': 0, 'results': []}, json_dumps_params={'ensure_ascii': False})

    q_lower = query.lower()
    results = []

    # Search active water products
    for w in Product.objects.filter(is_active=True, kind=Product.WATER):
        text_corp = f"{w.name} {w.search_text or ''} {w.description or ''}".lower()
        if q_lower in text_corp:
            photo_url = w.photo.url if w.photo else '/static/images/bottle.jpeg'
            results.append({
                'type': 'water',
                'id': w.pk,
                'name': w.name,
                'price': str(w.price),
                'volume': f"{w.volume:g} л" if w.volume else "19 л",
                'stock': w.stock,
                'in_stock': w.stock > 0,
                'photo': photo_url,
                'url': reverse('product_detail', kwargs={'pk': w.pk}),
            })
            if len(results) >= 6:
                break

    # Search coolers
    cooler_count = 0
    for c in Cooler.objects.all():
        text_corp = f"{c.name} {c.description or ''}".lower()
        if q_lower in text_corp:
            photo_url = c.photo.url if c.photo else '/static/images/cooler.jpeg'
            results.append({
                'type': 'cooler',
                'id': c.pk,
                'name': c.name,
                'price': f"{c.monthly_price:g} ₽/мес",
                'volume': 'Аренда кулера',
                'stock': c.quantity,
                'in_stock': c.quantity > 0,
                'photo': photo_url,
                'url': reverse('cooler_detail', kwargs={'pk': c.pk}),
            })
            cooler_count += 1
            if cooler_count >= 3:
                break

    return JsonResponse({
        'query': query,
        'count': len(results),
        'results': results,
    }, json_dumps_params={'ensure_ascii': False})


def api_quickview(request, pk):
    product = Product.objects.filter(pk=pk, is_active=True).first()
    if not product:
        return JsonResponse({'error': 'Товар не найден'}, status=404)
    photo_url = product.photo.url if product.photo else '/static/images/bottle.jpeg'
    return JsonResponse({
        'id': product.pk,
        'name': product.name,
        'price': str(product.price),
        'deposit_price': str(product.deposit_price or 0),
        'volume': f"{product.volume:g} л" if product.volume else "19 л",
        'stock': product.stock,
        'in_stock': product.stock > 0,
        'description': product.description or 'Чистая питьевая вода в оборотной бутыли 19 л. Подходит для кулера и ежедневного использования.',
        'photo': photo_url,
        'url': reverse('product_detail', kwargs={'pk': product.pk}),
        'add_cart_url': reverse('cart_add', kwargs={'pk': product.pk}),
    }, json_dumps_params={'ensure_ascii': False})

