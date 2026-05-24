from decimal import Decimal

from shop_epower.suppliers.models import CategoryMarkup, GlobalMarkup


def get_markup_percent_for_product(product) -> Decimal:
    category = product.category

    while category:
        category_markup = CategoryMarkup.objects.filter(
            category=category,
            is_active=True,
        ).first()

        if category_markup:
            return category_markup.percent

        category = category.parent

    global_markup = GlobalMarkup.objects.first()

    if global_markup:
        return global_markup.percent

    return Decimal("0")