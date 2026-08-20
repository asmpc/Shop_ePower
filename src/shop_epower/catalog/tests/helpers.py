from decimal import Decimal

from shop_epower.catalog.models import Brand, Category, Product


def create_test_brand(
    *,
    name="Test Brand",
    slug=None,
    **kwargs,
):
    return Brand.objects.create(
        name=name,
        slug=slug or "",
        **kwargs,
    )


def create_test_category(
    *,
    name="Test Category",
    slug=None,
    parent=None,
    **kwargs,
):
    return Category.objects.create(
        name=name,
        slug=slug or "",
        parent=parent,
        **kwargs,
    )


def create_test_product(
    *,
    name="Test Product",
    slug=None,
    brand=None,
    category=None,
    brand_name="Test Brand",
    category_name="Test Category",
    manufacturer_article="TEST-001",
    base_price=Decimal("10.00"),
    **kwargs,
):
    if brand is None:
        brand = create_test_brand(
            name=brand_name,
        )

    if category is None:
        category = create_test_category(
            name=category_name,
        )

    return Product.objects.create(
        name=name,
        slug=slug or "",
        brand=brand,
        category=category,
        manufacturer_article=manufacturer_article,
        base_price=base_price,
        **kwargs,
    )