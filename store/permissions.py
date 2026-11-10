from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

DISPATCHER_GROUP = 'Диспетчер'
DRIVER_GROUP = 'Водитель'


def is_dispatcher(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.groups.filter(name=DISPATCHER_GROUP).exists()


def is_driver(user):
    return user.is_authenticated and user.groups.filter(name=DRIVER_GROUP).exists()


def is_staff_member(user):
    return is_dispatcher(user) or is_driver(user)


def role_required(check):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
