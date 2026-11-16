from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.utils import timezone

from .models import Address, ContainerBalance, DeliverySlot, Profile, SanitationRequest

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


class OrderForm(forms.Form):
    address = forms.ModelChoiceField(queryset=Address.objects.none(), label='Адрес доставки')
    delivery_date = forms.DateField(label='Дата доставки', widget=DateInput())
    slot = forms.ModelChoiceField(queryset=DeliverySlot.objects.all(), label='Интервал доставки')
    returned_bottles = forms.IntegerField(label='Сколько пустых бутылей сдаёте курьеру', min_value=0, initial=0)
    comment = forms.CharField(label='Комментарий курьеру', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, user, bottles_total, **kwargs):
        super().__init__(*args, **kwargs)
        self.bottles_total = bottles_total
        self.balance = ContainerBalance.objects.filter(user=user).values_list('bottles', flat=True).first() or 0
        self.fields['address'].queryset = Address.objects.filter(user=user).select_related('district')
        self.fields['returned_bottles'].help_text = (
            f'У вас на руках бутылей: {self.balance}. Можно сдать не больше {self.balance + bottles_total}.'
        )

    def clean(self):
        data = super().clean()
        address = data.get('address')
        slot = data.get('slot')
        date = data.get('delivery_date')
        returned = data.get('returned_bottles')
        if date and date < timezone.localdate():
            self.add_error('delivery_date', 'Нельзя выбрать прошедшую дату.')
        if address and slot and not slot.districts.filter(pk=address.district_id).exists():
            self.add_error('slot', 'В этот район в выбранный интервал мы не доставляем.')
        if returned is not None and returned > self.balance + self.bottles_total:
            self.add_error('returned_bottles', 'Вы не можете сдать больше бутылей, чем у вас есть.')
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
