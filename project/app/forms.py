from datetime import timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import (Address, ContainerBalance, Cooler, DeliverySchedule, DeliverySlot, District,
                     Product, Profile, SanitationRequest)
from .validators import validate_image

User = get_user_model()


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, **kwargs):
        super().__init__(format='%Y-%m-%d', **kwargs)


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label='Электронная почта')
    phone = forms.CharField(label='Телефон', max_length=20)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'phone')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Пользователь с такой почтой уже зарегистрирован.')
        return email

    def save(self, commit=True):
        with transaction.atomic():
            user = super().save(commit=True)
            Profile.objects.create(user=user, phone=self.cleaned_data['phone'])
            ContainerBalance.objects.create(user=user)
        return user


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['district', 'street', 'house', 'flat', 'comment']
        error_messages = {
            'district': {
                'required': 'Пожалуйста, выберите район города из списка.',
            },
            'street': {
                'required': 'Укажите улицу доставки.',
            },
            'house': {
                'required': 'Укажите номер дома или строения.',
            },
        }

    def clean_street(self):
        street = self.cleaned_data.get('street', '').strip()
        if len(street) < 2:
            raise forms.ValidationError('Укажите корректное название улицы (не менее 2 символов).')
        return street

    def clean_house(self):
        house = self.cleaned_data.get('house', '').strip()
        if not house:
            raise forms.ValidationError('Укажите номер дома или строения.')
        if not any(c.isdigit() for c in house):
            raise forms.ValidationError('Номер дома должен содержать хотя бы одну цифру (например: 10, 14к2 или 5А).')
        return house


class OrderForm(forms.Form):
    address = forms.ModelChoiceField(queryset=Address.objects.none(), label='Адрес доставки')
    delivery_date = forms.DateField(label='Дата доставки', widget=DateInput())
    slot = forms.ModelChoiceField(queryset=DeliverySlot.objects.all(), label='Интервал доставки')
    returned_bottles = forms.IntegerField(label='Сколько пустых бутылей сдаёте курьеру', initial=0)
    comment = forms.CharField(label='Комментарий курьеру', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, user, bottles_total, **kwargs):
        super().__init__(*args, **kwargs)
        self.bottles_total = bottles_total
        self.balance = ContainerBalance.objects.filter(user=user).values_list('bottles', flat=True).first() or 0
        self.fields['address'].queryset = Address.objects.filter(user=user).select_related('district')
        self.fields['returned_bottles'].help_text = (
            f'У вас на руках бутылей: {self.balance}. Можно сдать не больше {self.balance + bottles_total}.'
        )

    def clean_returned_bottles(self):
        returned = self.cleaned_data.get('returned_bottles')
        if returned is not None and returned < 0:
            raise forms.ValidationError('Количество возвращаемых бутылей не может быть отрицательным числом.')
        return returned

    def clean(self):
        data = super().clean()
        address = data.get('address')
        slot = data.get('slot')
        date = data.get('delivery_date')
        returned = data.get('returned_bottles')
        if date:
            if date < timezone.localdate():
                self.add_error('delivery_date', 'Нельзя выбрать прошедшую дату. Пожалуйста, укажите сегодняшнюю или будущую дату.')
            elif date > timezone.localdate() + timedelta(days=14):
                self.add_error('delivery_date', 'Дата доставки не может быть позже 14 дней от текущей даты. Заказы оформляются не более чем на 2 недели вперёд.')
        if address and slot and not slot.districts.filter(pk=address.district_id).exists():
            self.add_error('slot', 'В выбранный район доставка в указанный интервал не осуществляется. Пожалуйста, выберите другой интервал или измените адрес доставки.')
        if returned is not None and returned > self.balance + self.bottles_total:
            self.add_error('returned_bottles', f'Вы не можете сдать больше {self.balance + self.bottles_total} бутылей (баланс: {self.balance}, в заказе: {self.bottles_total}). Укажите корректное количество.')
        return data


class RentalForm(forms.Form):
    address = forms.ModelChoiceField(queryset=Address.objects.none(), label='Куда установить кулер')
    start_date = forms.DateField(label='Дата начала аренды', widget=DateInput())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].queryset = Address.objects.filter(user=user).select_related('district')

    def clean_start_date(self):
        date = self.cleaned_data['start_date']
        if date < timezone.localdate():
            raise forms.ValidationError('Нельзя выбрать прошедшую дату.')
        return date


class SanitationForm(forms.ModelForm):
    class Meta:
        model = SanitationRequest
        fields = ['desired_date', 'photo', 'comment']
        widgets = {
            'desired_date': DateInput(),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }

    def clean_desired_date(self):
        date = self.cleaned_data['desired_date']
        if date < timezone.localdate():
            raise forms.ValidationError('Нельзя выбрать прошедшую дату.')
        return date


class DeliveryScheduleForm(forms.ModelForm):
    class Meta:
        model = DeliverySchedule
        fields = ['address', 'product', 'quantity', 'slot', 'weekday', 'is_active']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 1, 'max': 50}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['address'].queryset = Address.objects.filter(user=user).select_related('district')
        self.fields['product'].queryset = Product.objects.filter(kind=Product.WATER, is_active=True)
        self.fields['slot'].queryset = DeliverySlot.objects.all()

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if not qty or qty < 1 or qty > 50:
            raise forms.ValidationError('Укажите количество от 1 до 50 бутылей.')
        return qty


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'kind', 'volume', 'price', 'deposit_price', 'stock', 'description', 'photo', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None or price <= 0:
            raise forms.ValidationError('Введите цену — число больше 0.')
        return price

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'size'):
            validate_image(photo)
        return photo


class CoolerForm(forms.ModelForm):
    class Meta:
        model = Cooler
        fields = ['name', 'monthly_price', 'deposit', 'quantity', 'description', 'photo']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }

    def clean_monthly_price(self):
        price = self.cleaned_data.get('monthly_price')
        if price is None or price <= 0:
            raise forms.ValidationError('Введите стоимость аренды — число больше 0.')
        return price

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'size'):
            validate_image(photo)
        return photo


class DeliverySlotForm(forms.ModelForm):
    class Meta:
        model = DeliverySlot
        fields = ['start', 'end', 'districts']
        widgets = {
            'start': forms.TimeInput(attrs={'type': 'time'}),
            'end': forms.TimeInput(attrs={'type': 'time'}),
            'districts': forms.CheckboxSelectMultiple(),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        if start and end and start >= end:
            self.add_error('end', 'Время окончания интервала доставки должно быть строго позже времени начала.')
        return cleaned_data


class DistrictForm(forms.ModelForm):
    class Meta:
        model = District
        fields = ['name']


class UserEditForm(forms.ModelForm):
    phone = forms.CharField(label='Телефон', max_length=20, required=False)
    role = forms.ChoiceField(
        label='Роль в системе',
        choices=[
            ('client', 'Клиент'),
            ('dispatcher', 'Оператор / Диспетчер'),
            ('driver', 'Курьер / Водитель'),
            ('admin', 'Администратор'),
        ]
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
            if profile:
                self.fields['phone'].initial = profile.phone
            if self.instance.is_superuser:
                self.fields['role'].initial = 'admin'
            elif self.instance.groups.filter(name='Диспетчер').exists():
                self.fields['role'].initial = 'dispatcher'
            elif self.instance.groups.filter(name='Водитель').exists():
                self.fields['role'].initial = 'driver'
            else:
                self.fields['role'].initial = 'client'


class SiteSettingForm(forms.Form):
    first_order_discount = forms.IntegerField(
        label='Скидка на первый заказ (%)',
        min_value=0,
        max_value=100,
        initial=10,
        help_text='Процент автоматической скидки для новых клиентов'
    )
    min_order_bottles = forms.IntegerField(
        label='Минимальный объём заказа (бутылей 19 л)',
        min_value=1,
        max_value=20,
        initial=2
    )
    delivery_note = forms.CharField(
        label='Текст уведомления об условиях доставки',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        initial='Бесплатная доставка от 2 бутылей воды 19 л во все районы города.'
    )
