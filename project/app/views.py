from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import AddressForm, OrderForm, RegisterForm, RentalForm, SanitationForm
from .helpers import get_own, paginate, safe_next, to_decimal, to_int
from .models import Address, ContainerBalance, Cooler, Order, Product, Rental
from .permissions import is_dispatcher

PRODUCT_SORTS = [
    ('name', 'Название А–Я'),
    ('-name', 'Название Я–А'),
    ('price', 'Цена по возрастанию'),
    ('-price', 'Цена по убыванию'),
    ('volume', 'Объём по возрастанию'),
    ('-volume', 'Объём по убыванию'),
]

ORDER_SORTS = [
    ('-created_at', 'Сначала новые'),
    ('created_at', 'Сначала старые'),
    ('-total', 'Сумма по убыванию'),
    ('total', 'Сумма по возрастанию'),
    ('status', 'По статусу'),
    ('delivery_date', 'По дате доставки'),
]


def home(request):
    popular_waters = Product.objects.filter(is_active=True, kind=Product.WATER)[:3]
    coolers = Cooler.objects.all()[:3]
    return render(request, 'app/home.html', {
        'popular_waters': popular_waters,
        'coolers': coolers,
    })


def catalog(request):
    products = Product.objects.filter(is_active=True)
    query = request.GET.get('q', '').strip()
    kind = request.GET.get('kind', '').strip()
    volume = request.GET.get('volume', '').strip()
    price_min = to_decimal(request.GET.get('price_min'))
    price_max = to_decimal(request.GET.get('price_max'))
    only_available = request.GET.get('available') == '1'
    sort = request.GET.get('sort', 'popular')

    if query:
        products = products.filter(search_text__contains=query.lower())
    if kind in (Product.WATER, Product.COOLER):
        products = products.filter(kind=kind)
    else:
        products = products.filter(kind__in=[Product.WATER, Product.COOLER])
    if volume:
        try:
            vol_val = float(volume.replace(',', '.'))
            products = products.filter(volume=vol_val)
        except ValueError:
            pass
    if price_min is not None:
        products = products.filter(price__gte=price_min)
    if price_max is not None:
        products = products.filter(price__lte=price_max)
    if only_available:
        products = products.filter(stock__gt=0)

    if sort == 'popular':
        order_fields = ['-pk']
    elif sort in dict(PRODUCT_SORTS):
        order_fields = [sort, 'pk']
    else:
        order_fields = ['name', 'pk']

    page = paginate(request, products.order_by(*order_fields))
    return render(request, 'app/catalog.html', {
        'page': page,
        'query': query,
        'kind': kind,
        'volume': volume,
        'price_min': request.GET.get('price_min', ''),
        'price_max': request.GET.get('price_max', ''),
        'only_available': only_available,
        'sort': sort,
        'sort_options': PRODUCT_SORTS,
        'kinds': [('water', 'Вода'), ('cooler', 'Кулеры')],
        'total_count': products.count(),
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    return render(request, 'app/product_detail.html', {'product': product})


def register(request):
    if request.user.is_authenticated:
        return redirect('catalog')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        services.notify(user, 'Добро пожаловать в «Святой источник»',
                        f'Здравствуйте, {user.username}! Вы зарегистрированы, теперь можно заказывать воду и арендовать кулер.')
        messages.success(request, 'Регистрация прошла успешно.')
        return redirect('catalog')
    return render(request, 'app/register.html', {'form': form})


@login_required
def profile(request):
    balance_obj = ContainerBalance.objects.filter(user=request.user).first()
    bottles_count = balance_obj.bottles if balance_obj else 0
    deposit_amount = bottles_count * 350
    active_orders = Order.objects.filter(user=request.user).exclude(status=Order.DELIVERED)
    active_orders_count = active_orders.count()
    active_rentals = Rental.objects.filter(user=request.user, status=Rental.ACTIVE).count()
    last_order = Order.objects.filter(user=request.user).select_related('address', 'slot').order_by('-created_at').first()

    return render(request, 'app/profile.html', {
        'balance': bottles_count,
        'deposit_amount': deposit_amount,
        'active_orders_count': active_orders_count,
        'active_rentals': active_rentals,
        'last_order': last_order,
        'phone': getattr(getattr(request.user, 'profile', None), 'phone', ''),
    })


def cart(request):
    lines = services.cart_lines(request)
    return render(request, 'app/cart.html', {
        'lines': [(product, quantity, product.price * quantity) for product, quantity in lines],
        'totals': services.calculate_order(lines, 0),
    })


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    quantity = to_int(request.POST.get('quantity'), 1) or 1
    if product.stock < 1:
        messages.error(request, 'Этого товара сейчас нет на складе.')
    else:
        services.add_to_cart(request, product, quantity)
        messages.success(request, f'«{product.name}» добавлена в корзину.')
    return redirect(safe_next(request, 'catalog'))


@require_POST
def cart_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    services.set_cart_quantity(request, product, to_int(request.POST.get('quantity')))
    return redirect('cart')


def lines_of_order(order):
    return [(item.product, item.quantity) for item in order.items.select_related('product')]


def order_page(request, form, lines, order=None):
    returned = to_int(form['returned_bottles'].value()) if form.is_bound else 0
    totals = services.calculate_order(lines, returned)
    return render(request, 'app/checkout.html', {
        'form': form,
        'order': order,
        'lines': [(product, quantity, product.price * quantity) for product, quantity in lines],
        'totals': totals,
    })


@login_required
def checkout(request):
    lines = services.cart_lines(request)
    if not lines:
        messages.info(request, 'Сначала добавьте товары в корзину.')
        return redirect('catalog')
    if not Address.objects.filter(user=request.user).exists():
        messages.info(request, 'Добавьте адрес доставки, чтобы оформить заказ.')
        return redirect('address_create')

    bottles = services.calculate_order(lines, 0)['bottles']
    form = OrderForm(request.POST or None, user=request.user, bottles_total=bottles)
    if request.method == 'POST' and form.is_valid():
        try:
            order = services.create_order(request.user, lines, form.cleaned_data)
        except services.ServiceError as error:
            form.add_error(None, str(error))
        else:
            request.session['cart'] = {}
            services.notify(request.user, f'Заказ №{order.pk} оформлен',
                            f'Доставим {order.delivery_date:%d.%m.%Y} в интервале {order.slot}. К оплате: {order.total} ₽.')
            messages.success(request, f'Заказ №{order.pk} оформлен.')
            return redirect('order_detail', pk=order.pk)
    return order_page(request, form, lines)


def can_view_order(user, order):
    if order.user_id == user.id or is_dispatcher(user):
        return True
    return bool(order.route_sheet_id and order.route_sheet.driver_id == user.id)


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).select_related('address__district', 'slot')
    status = request.GET.get('status', '')
    sort = request.GET.get('sort', '-created_at')
    if status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)
    if sort not in dict(ORDER_SORTS):
        sort = '-created_at'
    page = paginate(request, orders.order_by(sort, 'pk'))
    return render(request, 'app/my_orders.html', {
        'page': page,
        'status': status,
        'sort': sort,
        'statuses': Order.STATUS_CHOICES,
        'sort_options': ORDER_SORTS,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('address__district', 'slot', 'route_sheet__driver', 'user'), pk=pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    return render(request, 'app/order_detail.html', {'order': order, 'items': order.items.select_related('product')})


@login_required
def order_edit(request, pk):
    order = get_own(Order, pk, request.user)
    if not order.is_new:
        messages.error(request, 'Заказ уже передан водителю, изменить его нельзя.')
        return redirect('order_detail', pk=order.pk)

    lines = lines_of_order(order)
    initial = {
        'address': order.address,
        'slot': order.slot,
        'delivery_date': order.delivery_date,
        'returned_bottles': order.returned_bottles,
        'comment': order.comment,
    }
    form = OrderForm(request.POST or None, initial=initial, user=request.user, bottles_total=order.bottles_total)
    if request.method == 'POST' and form.is_valid():
        services.update_order(order, form.cleaned_data)
        messages.success(request, 'Заказ изменён.')
        return redirect('order_detail', pk=order.pk)
    return order_page(request, form, lines, order)


@login_required
def order_delete(request, pk):
    order = get_own(Order, pk, request.user)
    if not order.is_new:
        messages.error(request, 'Заказ уже передан водителю, удалить его нельзя.')
        return redirect('order_detail', pk=order.pk)
    if request.method == 'POST':
        services.delete_order(order)
        messages.success(request, 'Заказ удалён, товары вернулись на склад.')
        return redirect('my_orders')
    return render(request, 'app/confirm_delete.html', {
        'title': f'Удалить заказ №{order.pk}?',
        'back': 'order_detail',
        'back_pk': order.pk,
    })


@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user).select_related('district')
    return render(request, 'app/address_list.html', {'addresses': addresses})


@login_required
def address_create(request):
    form = AddressForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, 'Адрес добавлен.')
        return redirect('address_list')
    return render(request, 'app/address_form.html', {'form': form, 'title': 'Новый адрес'})


@login_required
def address_edit(request, pk):
    address = get_own(Address, pk, request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Адрес изменён.')
        return redirect('address_list')
    return render(request, 'app/address_form.html', {'form': form, 'title': 'Изменить адрес'})


@login_required
def address_delete(request, pk):
    address = get_own(Address, pk, request.user)
    if request.method == 'POST':
        try:
            address.delete()
        except ProtectedError:
            messages.error(request, 'Адрес используется в заказах или договорах, удалить его нельзя.')
        else:
            messages.success(request, 'Адрес удалён.')
        return redirect('address_list')
    return render(request, 'app/confirm_delete.html', {
        'title': f'Удалить адрес «{address}»?',
        'back': 'address_list',
    })


def coolers(request):
    return render(request, 'app/coolers.html', {'coolers': Cooler.objects.all()})


@login_required
def rent_cooler(request, pk):
    cooler = get_object_or_404(Cooler, pk=pk)
    if not Address.objects.filter(user=request.user).exists():
        messages.info(request, 'Сначала добавьте адрес, куда привезти кулер.')
        return redirect('address_create')
    form = RentalForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            rental = services.rent_cooler(request.user, cooler, form.cleaned_data['address'], form.cleaned_data['start_date'])
        except services.ServiceError as error:
            form.add_error(None, str(error))
        else:
            services.notify(request.user, f'Договор аренды №{rental.pk}',
                            f'Кулер «{cooler.name}» будет установлен {rental.start_date:%d.%m.%Y}. Аренда {rental.monthly_price} ₽ в месяц.')
            messages.success(request, 'Договор аренды оформлен.')
            return redirect('my_rentals')
    return render(request, 'app/rent_form.html', {'form': form, 'cooler': cooler})


@login_required
def my_rentals(request):
    rentals = Rental.objects.filter(user=request.user).select_related('cooler', 'address__district')
    return render(request, 'app/my_rentals.html', {'rentals': rentals})


@login_required
def sanitation(request, pk):
    rental = get_own(Rental, pk, request.user)
    if rental.status != Rental.ACTIVE:
        messages.error(request, 'Санитарная обработка доступна только по действующему договору.')
        return redirect('my_rentals')
    form = SanitationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.rental = rental
        item.save()
        messages.success(request, 'Заявка на санитарную обработку принята.')
        return redirect('sanitation', pk=rental.pk)
    return render(request, 'app/sanitation.html', {
        'rental': rental,
        'form': form,
        'requests': rental.sanitations.all(),
    })
