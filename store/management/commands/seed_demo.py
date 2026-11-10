import random
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from store.models import (Address, ContainerBalance, Cooler, DeliverySlot, District, Order, OrderItem, Product,
                          Profile, Rental, RouteSheet)
from store.permissions import DISPATCHER_GROUP, DRIVER_GROUP
from store.services import calculate_order

User = get_user_model()

DISTRICTS = ['Центральный', 'Северный', 'Южный', 'Заречье', 'Академический', 'Железнодорожный']
STREETS = ['Ленина', 'Мира', 'Садовая', 'Новая', 'Гагарина', 'Речная', 'Школьная', 'Лесная', 'Победы', 'Парковая']
BRANDS = ['Родник', 'Серебряный ключ', 'Горная', 'Байкальская', 'Альпика', 'Тихий ручей']
WATER_TYPES = [('питьевая негазированная', 220), ('артезианская', 280), ('минеральная', 340)]
PUMPS = [('Помпа механическая', 450), ('Помпа электрическая', 1100), ('Помпа с подсветкой', 1500),
         ('Помпа настольная', 900), ('Помпа аккумуляторная', 1700)]
COOLERS = [('Кулер напольный Aqua Classic', 450, 2500, 6), ('Кулер настольный Aqua Mini', 320, 1800, 5),
           ('Кулер с холодильником Aqua Cool', 650, 3500, 4), ('Кулер с нагревом Aqua Hot', 520, 3000, 5),
           ('Кулер офисный Aqua Office', 780, 4000, 3), ('Кулер с генератором льда Aqua Ice', 990, 5000, 2)]


def get_or_create_user(username, password, superuser=False):
    user = User.objects.filter(username=username).first()
    if user:
        return user
    email = f'{username}@example.com'
    if superuser:
        return User.objects.create_superuser(username, email, password)
    return User.objects.create_user(username, email, password)


class Command(BaseCommand):
    help = 'Загружает демонстрационные данные для сайта доставки воды'

    @transaction.atomic
    def handle(self, *args, **options):
        if Product.objects.exists():
            self.stdout.write('Демонстрационные данные уже загружены.')
            return

        random.seed(6)
        dispatcher_group, _ = Group.objects.get_or_create(name=DISPATCHER_GROUP)
        driver_group, _ = Group.objects.get_or_create(name=DRIVER_GROUP)

        get_or_create_user('admin', 'admin12345', superuser=True)
        get_or_create_user('dispatcher', 'demo12345').groups.add(dispatcher_group)
        drivers = []
        for number in (1, 2):
            driver = get_or_create_user(f'driver{number}', 'demo12345')
            driver.groups.add(driver_group)
            drivers.append(driver)

        districts = [District.objects.create(name=name) for name in DISTRICTS]
        slots = []
        for start_hour in (9, 12, 15, 18):
            slot = DeliverySlot.objects.create(start=time(start_hour), end=time(start_hour + 3))
            slot.districts.set(random.sample(districts, 4) if start_hour == 18 else districts)
            slots.append(slot)

        products = []
        for brand in BRANDS:
            for kind_name, price in WATER_TYPES:
                products.append(Product.objects.create(
                    name=f'Вода «{brand}» {kind_name}, 19 л',
                    kind=Product.WATER,
                    volume=19,
                    price=price,
                    deposit_price=300,
                    stock=200,
                    description=f'Вода {kind_name}, {brand}.',
                ))
        for name, price in PUMPS:
            products.append(Product.objects.create(
                name=name, kind=Product.PUMP, price=price, stock=50,
                description='Для бутылей 19 л.',
            ))
        waters = [product for product in products if product.kind == Product.WATER]

        coolers = [
            Cooler.objects.create(name=name, monthly_price=price, deposit=deposit, quantity=quantity,
                                  description='Для дома и офиса.')
            for name, price, deposit, quantity in COOLERS
        ]

        clients = []
        addresses = []
        for number in range(1, 13):
            client = User.objects.create_user(f'client{number}', f'client{number}@example.com', 'demo12345')
            Profile.objects.create(user=client, phone=f'+7900{1000000 + number * 1111}')
            ContainerBalance.objects.create(user=client, bottles=random.randint(0, 6))
            clients.append(client)
            for _ in range(random.randint(1, 2)):
                addresses.append(Address.objects.create(
                    user=client,
                    district=random.choice(districts),
                    street=random.choice(STREETS),
                    house=str(random.randint(1, 80)),
                    flat=str(random.randint(1, 150)),
                ))

        today = timezone.localdate()
        for _ in range(36):
            address = random.choice(addresses)
            slot = random.choice(list(address.district.slots.all()))
            date = today + timedelta(days=random.randint(-14, 4))
            lines = [(product, random.randint(1, 4)) for product in random.sample(waters, random.randint(1, 2))]
            if random.random() < 0.3:
                lines.append((random.choice(products[-5:]), 1))
            bottles = calculate_order(lines, 0)['bottles']
            returned = random.randint(0, bottles)
            totals = calculate_order(lines, returned)

            order = Order.objects.create(
                user=address.user,
                address=address,
                slot=slot,
                delivery_date=date,
                returned_bottles=returned,
                bottles_total=totals['bottles'],
                goods_total=totals['goods'],
                deposit_total=totals['deposit'],
                total=totals['total'],
            )
            for product, quantity in lines:
                OrderItem.objects.create(order=order, product=product, quantity=quantity, price=product.price)

            if date < today:
                sheet, _ = RouteSheet.objects.get_or_create(driver=random.choice(drivers), date=date)
                order.route_sheet = sheet
                order.status = Order.DELIVERED
                order.delivered_at = timezone.now() - timedelta(days=(today - date).days)
                order.save()
            elif random.random() < 0.4:
                sheet, _ = RouteSheet.objects.get_or_create(driver=random.choice(drivers), date=date)
                order.route_sheet = sheet
                order.status = Order.ASSIGNED
                order.save()

        for client in random.sample(clients, 10):
            cooler = random.choice(coolers)
            Rental.objects.create(
                user=client,
                cooler=cooler,
                address=random.choice(list(client.addresses.all())),
                start_date=today - timedelta(days=random.randint(0, 60)),
                monthly_price=cooler.monthly_price,
                deposit=cooler.deposit,
            )

        self.stdout.write(self.style.SUCCESS('Данные загружены: admin/admin12345, dispatcher, driver1, driver2, client1–client12 (пароль demo12345).'))
