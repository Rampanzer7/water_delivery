from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import ContainerBalance, Cooler, Order, OrderItem, Product, Rental, RouteSheet


class ServiceError(Exception):
    pass


def notify(user, subject, text):
    if user.email:
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)


def cart_lines(request):
    cart = request.session.get('cart', {})
    products = Product.objects.filter(pk__in=[int(pk) for pk in cart], is_active=True).order_by('name')
    return [(product, cart[str(product.pk)]) for product in products]


def add_to_cart(request, product, quantity):
    cart = request.session.get('cart', {})
    key = str(product.pk)
    cart[key] = min(cart.get(key, 0) + quantity, product.stock)
    request.session['cart'] = cart


def set_cart_quantity(request, product, quantity):
    cart = request.session.get('cart', {})
    key = str(product.pk)
    if quantity <= 0:
        cart.pop(key, None)
    else:
        cart[key] = min(quantity, product.stock)
    request.session['cart'] = cart


def calculate_order(lines, returned_bottles):
    goods_total = Decimal('0')
    deposit_total = Decimal('0')
    bottles_total = 0
    returned_left = returned_bottles
    for product, quantity in lines:
        goods_total += product.price * quantity
        if product.kind == Product.WATER:
            bottles_total += quantity
            covered = min(returned_left, quantity)
            returned_left -= covered
            deposit_total += product.deposit_price * (quantity - covered)
    return {
        'bottles': bottles_total,
        'missing': max(bottles_total - returned_bottles, 0),
        'goods': goods_total,
        'deposit': deposit_total,
        'total': goods_total + deposit_total,
    }


@transaction.atomic
def create_order(user, lines, data):
    locked = Product.objects.select_for_update().in_bulk([product.pk for product, _ in lines])
    fresh_lines = []
    for product, quantity in lines:
        current = locked[product.pk]
        if current.stock < quantity:
            raise ServiceError(f'Товара «{current.name}» осталось только {current.stock} шт.')
        fresh_lines.append((current, quantity))

    totals = calculate_order(fresh_lines, data['returned_bottles'])
    order = Order.objects.create(
        user=user,
        address=data['address'],
        slot=data['slot'],
        delivery_date=data['delivery_date'],
        returned_bottles=data['returned_bottles'],
        bottles_total=totals['bottles'],
        goods_total=totals['goods'],
        deposit_total=totals['deposit'],
        total=totals['total'],
        comment=data.get('comment', ''),
    )
    for product, quantity in fresh_lines:
        OrderItem.objects.create(order=order, product=product, quantity=quantity, price=product.price)
        Product.objects.filter(pk=product.pk).update(stock=F('stock') - quantity)
    return order


@transaction.atomic
def update_order(order, data):
    items = list(order.items.select_related('product'))
    lines = [(item.product, item.quantity) for item in items]
    totals = calculate_order(lines, data['returned_bottles'])
    for item in items:
        item.price = item.product.price
        item.save(update_fields=['price'])
    order.address = data['address']
    order.slot = data['slot']
    order.delivery_date = data['delivery_date']
    order.returned_bottles = data['returned_bottles']
    order.bottles_total = totals['bottles']
    order.goods_total = totals['goods']
    order.deposit_total = totals['deposit']
    order.total = totals['total']
    order.comment = data.get('comment', '')
    order.save()
    return order


@transaction.atomic
def delete_order(order):
    for item in order.items.all():
        Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity)
    order.delete()


@transaction.atomic
def assign_order(order, driver):
    sheet, _ = RouteSheet.objects.get_or_create(driver=driver, date=order.delivery_date)
    order.route_sheet = sheet
    order.status = Order.ASSIGNED
    order.save(update_fields=['route_sheet', 'status'])
    return order


@transaction.atomic
def close_delivery(order_pk):
    order = Order.objects.select_for_update().get(pk=order_pk)
    if order.status != Order.ASSIGNED:
        raise ServiceError('Закрыть можно только доставку заказа, который передан водителю.')
    balance, _ = ContainerBalance.objects.select_for_update().get_or_create(user=order.user)
    balance.bottles = max(balance.bottles + order.bottles_total - order.returned_bottles, 0)
    balance.save(update_fields=['bottles'])
    order.status = Order.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=['status', 'delivered_at'])
    return order


@transaction.atomic
def rent_cooler(user, cooler, address, start_date):
    locked = Cooler.objects.select_for_update().get(pk=cooler.pk)
    if locked.quantity < 1:
        raise ServiceError('Кулеров этой модели сейчас нет в наличии.')
    Cooler.objects.filter(pk=locked.pk).update(quantity=F('quantity') - 1)
    return Rental.objects.create(
        user=user,
        cooler=locked,
        address=address,
        start_date=start_date,
        monthly_price=locked.monthly_price,
        deposit=locked.deposit,
    )
