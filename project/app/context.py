from .permissions import is_dispatcher, is_driver


def site_context(request):
    session = getattr(request, 'session', None)
    cart = session.get('cart', {}) if session is not None and hasattr(session, 'get') else {}
    user = getattr(request, 'user', None)
    is_auth = user.is_authenticated if user and hasattr(user, 'is_authenticated') else False
    return {
        'cart_count': sum(cart.values()) if isinstance(cart, dict) else 0,
        'user_is_dispatcher': is_dispatcher(user) if user else False,
        'user_is_driver': is_driver(user) if user else False,
        'user_is_admin': is_auth and (getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False)),
    }

