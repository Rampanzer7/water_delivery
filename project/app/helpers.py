from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme

PAGE_SIZE = 20


def to_decimal(value):
    try:
        number = Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def to_int(value, default=0):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def paginate(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get('page'))


def safe_next(request, default):
    target = request.POST.get('next', '')
    allowed = url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return target if target and allowed else default


def get_own(model, pk, user):
    obj = get_object_or_404(model, pk=pk)
    if obj.user_id != user.id:
        raise PermissionDenied
    return obj
