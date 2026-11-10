from .permissions import is_dispatcher, is_driver


def site_context(request):
    cart = request.session.get('cart', {})
    return {
        'cart_count': sum(cart.values()),
        'user_is_dispatcher': is_dispatcher(request.user),
        'user_is_driver': is_driver(request.user),
    }
