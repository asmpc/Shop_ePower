from decimal import Decimal, ROUND_HALF_UP

from shop_epower.suppliers.models import CurrencyRate


class CurrencyService:
    BASE_CURRENCY = "BYN"

    @classmethod
    def get_rate_to_byn(cls, currency: str) -> Decimal:
        currency = currency.upper()

        if currency == cls.BASE_CURRENCY:
            return Decimal("1")

        rate = CurrencyRate.objects.filter(
            currency=currency,
        ).first()

        if rate is None:
            raise ValueError(
                f"Currency rate for {currency} is not set."
            )

        return rate.rate_to_BYN

    @classmethod
    def convert(
        cls,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        amount = Decimal(amount)

        from_rate = cls.get_rate_to_byn(from_currency)
        to_rate = cls.get_rate_to_byn(to_currency)

        amount_in_byn = amount * from_rate
        converted = amount_in_byn / to_rate

        return converted.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def update_product_base_price(cls, product):
        from shop_epower.suppliers.models import SupplierProduct, GlobalMarkup

        supplier_products = SupplierProduct.objects.filter(
            product=product,
            is_active=True,
            supplier__is_active=True,
        ).exclude(
            supplier_price__isnull=True,
        )

        if not supplier_products.exists():
            return

        max_price_byn = max(
            cls.convert(
                amount=sp.supplier_price,
                from_currency=sp.currency,
                to_currency=cls.BASE_CURRENCY,
            )
            for sp in supplier_products
        )

        markup = GlobalMarkup.objects.first()
        markup_percent = markup.percent if markup else Decimal("20")

        product.base_price = (
            max_price_byn * (Decimal("1") + markup_percent / Decimal("100"))
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        product.save(update_fields=["base_price"])