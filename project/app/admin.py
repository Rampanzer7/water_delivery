from django.contrib import admin

from .models import (Address, ContainerBalance, Cooler, DeliverySlot, District, Order, OrderItem, Product,
                     Profile, Rental, RouteSheet, SanitationRequest)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'volume', 'price', 'deposit_price', 'stock', 'is_active']
    list_filter = ['kind', 'is_active']
    search_fields = ['name']


@admin.register(Cooler)
class CoolerAdmin(admin.ModelAdmin):
    list_display = ['name', 'monthly_price', 'deposit', 'quantity']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'delivery_date', 'slot', 'status', 'total']
    list_filter = ['status', 'delivery_date']
    search_fields = ['user__username']
    inlines = [OrderItemInline]


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'cooler', 'start_date', 'status']
    list_filter = ['status']


@admin.register(SanitationRequest)
class SanitationRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'rental', 'desired_date', 'status']
    list_filter = ['status']


@admin.register(ContainerBalance)
class ContainerBalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'bottles']


@admin.register(DeliverySlot)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ['start', 'end']
    filter_horizontal = ['districts']


admin.site.register(District)
admin.site.register(Address)
admin.site.register(Profile)
admin.site.register(RouteSheet)
