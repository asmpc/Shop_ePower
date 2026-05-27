from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.accounts.models import LegalProfile
from shop_epower.orders.models import Order, OrderStatus, OrderItem
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.cart.models import Cart, CartItem
from shop_epower.suppliers.models import Supplier, SupplierProduct
from django.core.exceptions import ValidationError
from shop_epower.orders.services import (
    create_order_from_cart,
    cancel_new_order,
)


User = get_user_model()


class TestsOrderModel(TestCase):

    # Проверяем, что заказ физлица может быть создан
    # без реквизитов юридического лица.
    def test_client_order_can_be_created_without_legal_fields(self):

        user = User.objects.create_user(
            email="client@example.com",
            username="client",
            password="testpass123",
        )

        order = Order.objects.create(
            user=user,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Client User",
            customer_email="client@example.com",
            customer_phone="+10000000000",
            total_price=Decimal("100.00"),
        )

        self.assertEqual(order.user, user)
        self.assertEqual(order.status, OrderStatus.NEW)
        self.assertFalse(order.is_legal_entity)

        self.assertEqual(order.company_name, "")
        self.assertEqual(order.tax_id, "")
        self.assertEqual(order.legal_address, "")
        self.assertEqual(order.bank_name, "")
        self.assertEqual(order.bank_account, "")

        self.assertEqual(order.total_price, Decimal("100.00"))

    # Проверяем, что заказ юрлица сохраняет snapshot реквизитов.
    # Реквизиты копируются прямо в Order, а не связываются с LegalProfile.
    def test_legal_entity_order_stores_legal_profile_snapshot(self):

        user = User.objects.create_user(
            email="legal@example.com",
            username="legal",
            password="testpass123",
        )

        order = Order.objects.create(
            user=user,
            status=OrderStatus.NEW,
            is_legal_entity=True,
            customer_name="Legal User",
            customer_email="legal@example.com",
            customer_phone="+10000000001",
            company_name="Test Company LLC",
            tax_id="123456789",
            legal_address="Legal address 1",
            bank_name="Test Bank",
            bank_account="40702810000000000001",
            total_price=Decimal("250.00"),
        )

        self.assertTrue(order.is_legal_entity)
        self.assertEqual(order.company_name, "Test Company LLC")
        self.assertEqual(order.tax_id, "123456789")
        self.assertEqual(order.legal_address, "Legal address 1")
        self.assertEqual(order.bank_name, "Test Bank")
        self.assertEqual(order.bank_account, "40702810000000000001")
        self.assertEqual(order.total_price, Decimal("250.00"))

    # Проверяем главный принцип snapshot:
    # если LegalProfile изменился после оформления заказа,
    # данные в уже созданном заказе не должны измениться.
    def test_order_does_not_change_if_legal_profile_changes(self):

        user = User.objects.create_user(
            email="snapshot@example.com",
            username="snapshot",
            password="testpass123",
        )

        legal_profile = LegalProfile.objects.create(
            user=user,
            is_legal_entity=True,
            company_name="Old Company",
            tax_id="111111111",
            legal_address="Old address",
            bank_name="Old Bank",
            bank_account="OLD_ACC",
        )

        order = Order.objects.create(
            user=user,
            status=OrderStatus.NEW,
            is_legal_entity=True,
            customer_name="Snapshot User",
            customer_email="snapshot@example.com",
            customer_phone="+10000000002",
            company_name=legal_profile.company_name,
            tax_id=legal_profile.tax_id,
            legal_address=legal_profile.legal_address,
            bank_name=legal_profile.bank_name,
            bank_account=legal_profile.bank_account,
            total_price=Decimal("300.00"),
        )

        legal_profile.company_name = "New Company"
        legal_profile.tax_id = "999999999"
        legal_profile.save()

        order.refresh_from_db()

        self.assertEqual(order.company_name, "Old Company")
        self.assertEqual(order.tax_id, "111111111")

    # Проверяем pricing snapshot:
    # цена товара в OrderItem фиксируется на момент заказа.
    # Если Product.base_price изменится позже, OrderItem.unit_price
    # должен остаться прежним.
    def test_order_item_price_snapshot(self):

        user = User.objects.create_user(
            email="price@example.com",
            username="price",
            password="testpass123",
        )

        brand = Brand.objects.create(
            name="Test Brand",
        )

        category = Category.objects.create(
            name="Test Category",
        )

        product = Product.objects.create(
            name="Test Product",
            brand=brand,
            category=category,
            manufacturer_article="TEST-001",
            base_price=Decimal("10.00"),
        )

        order = Order.objects.create(
            user=user,
            status=OrderStatus.NEW,
            is_legal_entity=False,
            customer_name="Price User",
            customer_email="price@example.com",
            customer_phone="+10000000003",
            total_price=Decimal("20.00"),
        )

        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.base_price,
            quantity=2,
            total_price=Decimal("20.00"),
        )

        product.base_price = Decimal("999.00")
        product.save()

        item.refresh_from_db()

        self.assertEqual(item.unit_price, Decimal("10.00"))

    # Проверяем checkout service для физлица:
    # заказ создаётся из корзины, данные пользователя копируются,
    # создаётся OrderItem, total_price считается по CartItem,
    # а корзина после checkout становится неактивной.
    def test_create_order_from_cart_for_client(self):

        user = User.objects.create_user(
            email="checkout@example.com",
            username="checkout",
            password="testpass123",
            phone="+10000000004",
        )

        brand = Brand.objects.create(
            name="Checkout Brand",
        )

        category = Category.objects.create(
            name="Checkout Category",
        )

        product = Product.objects.create(
            name="Checkout Product",
            brand=brand,
            category=category,
            manufacturer_article="CHECKOUT-001",
            base_price=Decimal("15.00"),
        )

        supplier = Supplier.objects.create(
            name="Own Warehouse",
            is_own=True,
            is_active=True,
        )

        supplier_product = SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="SUP-CHECKOUT-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("15.00"),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        cart.refresh_from_db()

        supplier_product.refresh_from_db()

        self.assertEqual(order.user, user)
        self.assertFalse(order.is_legal_entity)
        self.assertEqual(order.customer_email, "checkout@example.com")
        self.assertEqual(order.customer_phone, "+10000000004")
        # Проверяем, что доставка пока не используется:
        # заказ создаётся без адреса, потому что сейчас работает самовывоз.
        self.assertIsNone(order.delivery_address)
        self.assertEqual(order.total_price, Decimal("30.00"))

        self.assertEqual(order.items.count(), 1)

        order_item = order.items.first()

        self.assertEqual(order_item.product, product)
        self.assertEqual(order_item.product_name, "Checkout Product")
        self.assertEqual(order_item.unit_price, Decimal("15.00"))
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.total_price, Decimal("30.00"))

        self.assertFalse(cart.is_active)

        self.assertEqual(supplier_product.stock_quantity, 8)

        # Проверяем защиту от oversell:
        # если товара на складе меньше, чем в корзине,
        # checkout должен завершиться ошибкой.
        # Заказ не создаётся, корзина остаётся активной,
        # stock у поставщика не изменяется.
    def test_checkout_raises_error_when_not_enough_stock(self):
        user = User.objects.create_user(
            email="nostock@example.com",
            username="nostock",
            password="testpass123",
            phone="+10000000005",
        )

        brand = Brand.objects.create(
            name="No Stock Brand",
        )

        category = Category.objects.create(
            name="No Stock Category",
        )

        product = Product.objects.create(
            name="No Stock Product",
            brand=brand,
            category=category,
            manufacturer_article="NO-STOCK-001",
            base_price=Decimal("20.00"),
        )

        supplier = Supplier.objects.create(
            name="Own Warehouse No Stock",
            is_own=True,
            is_active=True,
        )

        supplier_product = SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="SUP-NO-STOCK-001",
            stock_quantity=1,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            price_snapshot=Decimal("20.00"),
        )

        with self.assertRaises(ValidationError):
            create_order_from_cart(
                user=user,
                cart=cart,
            )

        cart.refresh_from_db()
        supplier_product.refresh_from_db()

        self.assertTrue(cart.is_active)
        self.assertEqual(supplier_product.stock_quantity, 1)
        self.assertEqual(Order.objects.filter(user=user).count(), 0)

    # Проверяем порядок списания stock:
    # сначала checkout списывает товар с нашего склада (is_own=True),
    # а если там не хватает — добирает остаток у внешнего поставщика.
    def test_checkout_reserves_stock_from_own_supplier_first(self):
        user = User.objects.create_user(
            email="multistock@example.com",
            username="multistock",
            password="testpass123",
            phone="+10000000006",
        )

        brand = Brand.objects.create(
            name="Multi Stock Brand",
        )

        category = Category.objects.create(
            name="Multi Stock Category",
        )

        product = Product.objects.create(
            name="Multi Stock Product",
            brand=brand,
            category=category,
            manufacturer_article="MULTI-STOCK-001",
            base_price=Decimal("30.00"),
        )

        own_supplier = Supplier.objects.create(
            name="Own Warehouse Multi",
            is_own=True,
            is_active=True,
        )

        external_supplier = Supplier.objects.create(
            name="External Supplier Multi",
            is_own=False,
            is_active=True,
        )

        own_supplier_product = SupplierProduct.objects.create(
            supplier=own_supplier,
            product=product,
            supplier_article="OWN-MULTI-001",
            stock_quantity=2,
            lead_time_days=0,
            is_active=True,
        )

        external_supplier_product = SupplierProduct.objects.create(
            supplier=external_supplier,
            product=product,
            supplier_article="EXT-MULTI-001",
            stock_quantity=5,
            lead_time_days=3,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=4,
            price_snapshot=Decimal("30.00"),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        own_supplier_product.refresh_from_db()
        external_supplier_product.refresh_from_db()

        self.assertEqual(order.total_price, Decimal("120.00"))

        self.assertEqual(own_supplier_product.stock_quantity, 0)
        self.assertEqual(external_supplier_product.stock_quantity, 3)

    # Проверяем отмену нового заказа:
    # если заказ находится в статусе NEW, клиент может его отменить,
    # статус меняется на CANCELLED, а зарезервированный stock
    # возвращается обратно поставщику.
    def test_cancel_new_order_returns_reserved_stock(self):
        user = User.objects.create_user(
            email="cancel@example.com",
            username="cancel",
            password="testpass123",
            phone="+10000000008",
        )

        brand = Brand.objects.create(
            name="Cancel Brand",
        )

        category = Category.objects.create(
            name="Cancel Category",
        )

        product = Product.objects.create(
            name="Cancel Product",
            brand=brand,
            category=category,
            manufacturer_article="CANCEL-001",
            base_price=Decimal("40.00"),
        )

        supplier = Supplier.objects.create(
            name="Cancel Supplier",
            is_own=True,
            is_active=True,
        )

        supplier_product = SupplierProduct.objects.create(
            supplier=supplier,
            product=product,
            supplier_article="CANCEL-SUP-001",
            stock_quantity=10,
            lead_time_days=0,
            is_active=True,
        )

        cart = Cart.objects.create(
            user=user,
        )

        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=3,
            price_snapshot=Decimal("40.00"),
        )

        order = create_order_from_cart(
            user=user,
            cart=cart,
        )

        supplier_product.refresh_from_db()

        self.assertEqual(supplier_product.stock_quantity, 7)
        self.assertEqual(order.status, OrderStatus.NEW)

        cancelled_order = cancel_new_order(
            order=order,
            user=user,
        )

        supplier_product.refresh_from_db()
        cancelled_order.refresh_from_db()

        self.assertEqual(cancelled_order.status, OrderStatus.CANCELLED)
        self.assertEqual(supplier_product.stock_quantity, 10)