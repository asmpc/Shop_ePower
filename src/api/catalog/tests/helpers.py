from shop_epower.catalog.models import Brand, Category, Product


def create_test_brand(
    name="Test brand",
    slug="test-brand",
):
    return Brand.objects.create(
        name=name,
        slug=slug,
    )


def create_test_category(
    name="Test category",
    slug="test-category",
    parent=None,
):
    return Category.objects.create(
        name=name,
        slug=slug,
        parent=parent,
    )


def create_test_product(
    name="Test product",
    slug="test-product",
    brand=None,
    category=None,
    manufacturer_article="ART-001",
    base_price=100,
):
    if brand is None:
        brand = create_test_brand()

    if category is None:
        category = create_test_category()

    return Product.objects.create(
        name=name,
        slug=slug,
        brand=brand,
        category=category,
        manufacturer_article=manufacturer_article,
        base_price=base_price,
    )


def assert_inventory_structure(test_case, inventory):
    test_case.assertIn("own_stock", inventory)
    test_case.assertIn("supplier_stock", inventory)
    test_case.assertIn("total_available", inventory)
    test_case.assertIn("min_lead_time", inventory)
    test_case.assertIn("in_stock", inventory)