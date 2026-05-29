from decimal import Decimal

from django.contrib.auth import get_user_model

from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.cart.models import Cart, CartItem
from shop_epower.suppliers.models import Supplier, SupplierProduct


User = get_user_model()


def create_test_user(
    *,
    email="user@example.com",
    username="user",
    password="testpass123",
    phone="+10000000000",
):
    return User.objects.create_user(
        email=email,
        username=username,
        password=password,
        phone=phone,
    )


def create_test_product(
    *,
    name="Test Product",
    brand_name="Test Brand",
    category_name="Test Category",
    manufacturer_article="TEST-001",
    base_price=Decimal("10.00"),
):
    brand = Brand.objects.create(
        name=brand_name,
    )

    category = Category.objects.create(
        name=category_name,
    )

    return Product.objects.create(
        name=name,
        brand=brand,
        category=category,
        manufacturer_article=manufacturer_article,
        base_price=base_price,
    )


def create_test_supplier(
    *,
    name="Own Warehouse",
    is_own=True,
    is_active=True,
):
    return Supplier.objects.create(
        name=name,
        is_own=is_own,
        is_active=is_active,
    )


def create_test_supplier_product(
    *,
    supplier,
    product,
    supplier_article="SUP-TEST-001",
    stock_quantity=10,
    lead_time_days=0,
    is_active=True,
):
    return SupplierProduct.objects.create(
        supplier=supplier,
        product=product,
        supplier_article=supplier_article,
        stock_quantity=stock_quantity,
        lead_time_days=lead_time_days,
        is_active=is_active,
    )


def create_test_cart_with_item(
    *,
    user,
    product,
    quantity=1,
    price_snapshot=Decimal("10.00"),
):
    cart = Cart.objects.create(
        user=user,
    )

    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=quantity,
        price_snapshot=price_snapshot,
    )

    return cart