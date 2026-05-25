from shop_epower.core.currency import get_base_currency


def base_currency(request):
    return {
        "base_currency": get_base_currency(),
    }