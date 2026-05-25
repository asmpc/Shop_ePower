from decimal import Decimal, ROUND_HALF_UP

from shop_epower.core.currency import get_base_currency
from shop_epower.suppliers.models import CurrencyRate, SupplierProduct
from shop_epower.suppliers.services.markup import get_markup_percent_for_product


class CurrencyService:

    @classmethod
    def get_base_currency(cls) -> str:
        return get_base_currency()

    @classmethod
    def get_rate_to_base_currency(cls, currency: str) -> Decimal:
        currency = currency.upper()
        base_currency = cls.get_base_currency()

        if currency == base_currency:
            return Decimal("1")

        rate = CurrencyRate.objects.filter(
            currency=currency,
        ).first()

        if rate is None:
            raise ValueError(
                f"Currency rate for {currency} is not set."
            )

        return rate.rate_to_base_currency

    @classmethod
    def convert(
        cls,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        amount = Decimal(amount)

        from_rate = cls.get_rate_to_base_currency(from_currency)
        to_rate = cls.get_rate_to_base_currency(to_currency)

        amount_in_base_currency = amount * from_rate
        converted = amount_in_base_currency / to_rate

        return converted.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def update_product_base_price(cls, product):
        supplier_products = SupplierProduct.objects.filter(
            product=product,
            is_active=True,
            supplier__is_active=True,
        ).exclude(
            supplier_price__isnull=True,
        )

        if not supplier_products.exists():
            return

        base_currency = cls.get_base_currency()

        max_price_in_base_currency = max(
            cls.convert(
                amount=sp.supplier_price,
                from_currency=sp.currency,
                to_currency=base_currency,
            )
            for sp in supplier_products
        )

        markup_percent = get_markup_percent_for_product(product)

        product.base_price = (
            max_price_in_base_currency
            * (Decimal("1") + markup_percent / Decimal("100"))
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        product.save(update_fields=["base_price"])