from django.conf import settings


def get_base_currency():
    """
    Возвращает базовую валюту проекта.
    Используется как единая точка доступа к настройке SHOP_BASE_CURRENCY.
    """
    return getattr(settings, "SHOP_BASE_CURRENCY", "BYN")