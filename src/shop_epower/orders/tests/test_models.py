from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.accounts.models import LegalProfile
from shop_epower.orders.models import Order, OrderStatus, OrderItem
from shop_epower.catalog.models import Brand, Category, Product


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