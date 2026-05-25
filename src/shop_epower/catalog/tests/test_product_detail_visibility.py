from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.models import User, Role
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.suppliers.models import Supplier, SupplierProduct



#роль пользователя управляет тем, какие данные попадают в context
class ProductDetailVisibilityTestCase(TestCase):

    # Подготавливаем базовые данные для тестов:
    # - продукт
    # - поставщик
    # - связь поставщика с продуктом (SupplierProduct)
    # Это нужно, чтобы проверить, кому доступны данные о поставщиках.
    def setUp(self):
        self.brand = Brand.objects.create(name="Test Brand")
        self.category = Category.objects.create(name="Test Category")

        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="VISIBILITY-001",
            base_price=100,
            is_active=True,
        )

        self.supplier = Supplier.objects.create(
            name="External Supplier",
            is_own=False,
            is_active=True,
        )

        self.supplier_product = SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.product,
            supplier_article="SUP-001",
            supplier_price=50,
            currency="BYN",
            stock_quantity=20,
            lead_time_days=5,
            is_active=True,
        )

    # Проверяем, что обычный пользователь (CLIENT)
    # не получает чувствительные данные о поставщиках:
    # - нет supplier_inventory_details
    # - нет cost_summary
    # Это важно для безопасности: клиент не должен видеть закупочные данные.
    def test_client_does_not_receive_supplier_inventory_details(self):
        client_user = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="testpass123",
            role=Role.CLIENT,
        )

        self.client.login(
            email="client@example.com",
            password="testpass123",
        )

        response = self.client.get(
            reverse("catalog:product_detail", kwargs={"slug": self.product.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_manager"])
        self.assertNotIn("supplier_inventory_details", response.context)
        self.assertNotIn("cost_summary", response.context)
        self.assertNotIn("supplier_price", str(response.content))

    # Проверяем, что менеджер (MANAGER)
    # получает расширенные данные:
    # - список supplier_inventory_details
    # - агрегированную cost_summary
    # Также проверяем, что данные соответствуют ожидаемым (supplier_product).
    def test_manager_receives_supplier_inventory_details(self):
        manager_user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123",
            role=Role.MANAGER,
        )

        self.client.login(
            email="manager@example.com",
            password="testpass123",
        )

        response = self.client.get(
            reverse("catalog:product_detail", kwargs={"slug": self.product.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_manager"])
        self.assertIn("supplier_inventory_details", response.context)
        self.assertEqual(
            list(response.context["supplier_inventory_details"]),
            [self.supplier_product],
        )
        self.assertIn("cost_summary", response.context)
        self.assertIsNotNone(response.context["cost_summary"])

    # Проверяем, что администратор (ADMIN)
    # имеет те же права доступа, что и менеджер:
    # - видит supplier_inventory_details
    # - видит cost_summary
    # Здесь важно, что ADMIN тоже считается "is_manager" в контексте.
    def test_admin_receives_supplier_inventory_details(self):
        admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role=Role.ADMIN,
        )

        self.client.login(
            email="admin@example.com",
            password="testpass123",
        )

        response = self.client.get(
            reverse("catalog:product_detail", kwargs={"slug": self.product.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_manager"])
        self.assertIn("supplier_inventory_details", response.context)
        self.assertIn("cost_summary", response.context)
        self.assertIsNotNone(response.context["cost_summary"])