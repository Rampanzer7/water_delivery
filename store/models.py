from django.conf import settings
from django.db import models

from .validators import validate_image


class District(models.Model):
    name = models.CharField('Название', max_length=100, unique=True)

    class Meta:
        verbose_name = 'Район'
        verbose_name_plural = 'Районы'
        ordering = ['name']

    def __str__(self):
        return self.name


class DeliverySlot(models.Model):
    start = models.TimeField('Начало')
    end = models.TimeField('Конец')
    districts = models.ManyToManyField(District, related_name='slots', verbose_name='Районы')

    class Meta:
        verbose_name = 'Интервал доставки'
        verbose_name_plural = 'Интервалы доставки'
        ordering = ['start']

    def __str__(self):
        return f'{self.start:%H:%M}–{self.end:%H:%M}'


class Product(models.Model):
    WATER = 'water'
    PUMP = 'pump'
    KIND_CHOICES = [(WATER, 'Вода'), (PUMP, 'Помпа')]

    name = models.CharField('Название', max_length=150)
    kind = models.CharField('Тип', max_length=10, choices=KIND_CHOICES, default=WATER)
    volume = models.DecimalField('Объём, л', max_digits=5, decimal_places=1, default=0)
    price = models.DecimalField('Цена', max_digits=8, decimal_places=2)
    deposit_price = models.DecimalField('Залог за бутыль', max_digits=8, decimal_places=2, default=0)
    stock = models.PositiveIntegerField('Остаток на складе', default=0)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Продаётся', default=True)
    search_text = models.TextField(editable=False, default='')

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.search_text = f'{self.name} {self.description}'.lower()
        super().save(*args, **kwargs)


class Cooler(models.Model):
    name = models.CharField('Модель', max_length=150)
    description = models.TextField('Описание', blank=True)
    monthly_price = models.DecimalField('Аренда в месяц', max_digits=8, decimal_places=2)
    deposit = models.DecimalField('Залог', max_digits=8, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField('Свободно на складе', default=0)

    class Meta:
        verbose_name = 'Кулер'
        verbose_name_plural = 'Кулеры'
        ordering = ['name']

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Телефон', max_length=20)

    class Meta:
        verbose_name = 'Профиль клиента'
        verbose_name_plural = 'Профили клиентов'

    def __str__(self):
        return f'{self.user.username}, {self.phone}'


class ContainerBalance(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='container_balance')
    bottles = models.PositiveIntegerField('Бутылей на руках у клиента', default=0)

    class Meta:
        verbose_name = 'Баланс тары'
        verbose_name_plural = 'Балансы тары'

    def __str__(self):
        return f'{self.user.username}: {self.bottles}'


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    district = models.ForeignKey(District, on_delete=models.PROTECT, verbose_name='Район')
    street = models.CharField('Улица', max_length=150)
    house = models.CharField('Дом', max_length=10)
    flat = models.CharField('Квартира или офис', max_length=10, blank=True)
    comment = models.CharField('Как пройти', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Адрес доставки'
        verbose_name_plural = 'Адреса доставки'
        ordering = ['id']

    def __str__(self):
        text = f'{self.district}, ул. {self.street}, д. {self.house}'
        if self.flat:
            text += f', кв. {self.flat}'
        return text


class RouteSheet(models.Model):
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='route_sheets')
    date = models.DateField('Дата')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Маршрутный лист'
        verbose_name_plural = 'Маршрутные листы'
        ordering = ['-date']
        constraints = [models.UniqueConstraint(fields=['driver', 'date'], name='one_sheet_per_driver_per_day')]

    def __str__(self):
        return f'Маршрут №{self.pk}, {self.driver.username}, {self.date:%d.%m.%Y}'


class Order(models.Model):
    NEW = 'new'
    ASSIGNED = 'assigned'
    DELIVERED = 'delivered'
    STATUS_CHOICES = [
        (NEW, 'Новый'),
        (ASSIGNED, 'У водителя'),
        (DELIVERED, 'Доставлен'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    address = models.ForeignKey(Address, on_delete=models.PROTECT, verbose_name='Адрес')
    slot = models.ForeignKey(DeliverySlot, on_delete=models.PROTECT, verbose_name='Интервал')
    delivery_date = models.DateField('Дата доставки')
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default=NEW)
    returned_bottles = models.PositiveIntegerField('Сдаётся пустых бутылей', default=0)
    bottles_total = models.PositiveIntegerField('Заказано бутылей', default=0)
    goods_total = models.DecimalField('Стоимость товаров', max_digits=10, decimal_places=2, default=0)
    deposit_total = models.DecimalField('Залог за тару', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('Итого', max_digits=10, decimal_places=2, default=0)
    route_sheet = models.ForeignKey(RouteSheet, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    delivered_at = models.DateTimeField('Доставлен', null=True, blank=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ №{self.pk}'

    @property
    def missing_bottles(self):
        return max(self.bottles_total - self.returned_bottles, 0)

    @property
    def is_new(self):
        return self.status == self.NEW


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Товар')
    quantity = models.PositiveIntegerField('Количество')
    price = models.DecimalField('Цена на момент заказа', max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product} × {self.quantity}'

    @property
    def subtotal(self):
        return self.price * self.quantity


class Rental(models.Model):
    ACTIVE = 'active'
    CLOSED = 'closed'
    STATUS_CHOICES = [(ACTIVE, 'Действует'), (CLOSED, 'Расторгнут')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='rentals')
    cooler = models.ForeignKey(Cooler, on_delete=models.PROTECT, verbose_name='Кулер')
    address = models.ForeignKey(Address, on_delete=models.PROTECT, verbose_name='Адрес установки')
    start_date = models.DateField('Начало аренды')
    monthly_price = models.DecimalField('Аренда в месяц', max_digits=8, decimal_places=2)
    deposit = models.DecimalField('Залог', max_digits=8, decimal_places=2, default=0)
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Договор аренды кулера'
        verbose_name_plural = 'Договоры аренды кулеров'
        ordering = ['-created_at']

    def __str__(self):
        return f'Договор №{self.pk}'


class SanitationRequest(models.Model):
    NEW = 'new'
    DONE = 'done'
    STATUS_CHOICES = [(NEW, 'Ожидает'), (DONE, 'Выполнена')]

    rental = models.ForeignKey(Rental, on_delete=models.CASCADE, related_name='sanitations')
    desired_date = models.DateField('Желаемая дата')
    photo = models.FileField('Фото кулера', upload_to='sanitation/', validators=[validate_image])
    comment = models.CharField('Комментарий', max_length=200, blank=True)
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default=NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка на санитарную обработку'
        verbose_name_plural = 'Заявки на санитарную обработку'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заявка №{self.pk}'
