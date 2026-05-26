from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from shop_epower.catalog.models import Product, Brand, Category
from django.core.files.uploadedfile import SimpleUploadedFile

from shop_epower.catalog.models import ProductImage
from django.contrib.auth import get_user_model

User = get_user_model()

class TestProductListAPI(APITestCase):

    # Проверяем, что API списка товаров возвращает созданные продукты
    def test_product_list_returns_products(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
        )

        response = self.client.get(
            reverse("api-product-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            response.data[0]["slug"],
            "test-product",
        )

    # Проверяем, что в списке товаров API возвращает не только базовые данные,
    # но и рассчитанную цену final_price и inventory.
    def test_product_list_returns_product_price_and_inventory(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
            base_price=100,
        )

        response = self.client.get(
            reverse("api-product-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[0]["slug"],
            "test-product",
        )

        self.assertIn(
            "final_price",
            response.data[0],
        )

        self.assertIn(
            "inventory",
            response.data[0],
        )

        self.assertEqual(
            response.data[0]["final_price"],
            "100.00",
        )

    # Проверяем detail endpoint товара:
    # возвращаются slug, final_price, inventory, brand и images.
    def test_product_detail_returns_product(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
            base_price=100,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["slug"],
            "test-product",
        )

        self.assertEqual(
            response.data["final_price"],
            "100.00",
        )

        self.assertIn(
            "inventory",
            response.data,
        )

        self.assertIn(
            "brand",
            response.data
        )

        self.assertIn(
            "images",
            response.data,
        )

    # Проверяем, что detail endpoint возвращает изображения товара
    # и при этом не отдаёт manager-only данные обычному пользователю.
    def test_product_detail_returns_images(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
            base_price=100,
        )

        image = SimpleUploadedFile(
            name="test.jpg",
            content=b"test image content",
            content_type="image/jpeg",
        )

        ProductImage.objects.create(
            product=product,
            image=image,
            alt_text="Test image",
            is_primary=True,
            sort_order=1,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["images"]),
            1,
        )

        self.assertEqual(
            response.data["images"][0]["alt_text"],
            "Test image",
        )

        self.assertTrue(
            response.data["images"][0]["is_primary"],
        )

        self.assertNotIn(
            "supplier_inventory_details",
            response.data
        )

        self.assertNotIn(
            "cost_summary",
            response.data
        )

    # Проверяем, что manager получает расширенные данные товара:
    # supplier_inventory_details и cost_summary.
    def test_product_detail_returns_manager_data_for_manager(self):
        user = User.objects.create_user(
            email="manager@test.com",
            username="manager",
            password="12345678",
            role="manager",
        )

        self.client.force_authenticate(user=user)

        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
            base_price=100,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("supplier_inventory_details", response.data)
        self.assertIn("cost_summary", response.data)

    # Проверяем фильтрацию списка товаров по brand slug.
    def test_product_list_can_filter_by_brand(self):
        brand_1 = Brand.objects.create(
            name="Brand 1",
            slug="brand-1",
        )
        brand_2 = Brand.objects.create(
            name="Brand 2",
            slug="brand-2",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        Product.objects.create(
            name="Product 1",
            slug="product-1",
            brand=brand_1,
            category=category,
            base_price=100,
        )

        Product.objects.create(
            name="Product 2",
            slug="product-2",
            brand=brand_2,
            category=category,
            base_price=100,
        )

        response = self.client.get(
            reverse("api-product-list"),
            {
                "brand": "brand-1",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["slug"],
            "product-1",
        )

    # Проверяем фильтрацию списка товаров по category slug.
    def test_product_list_can_filter_by_category(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category_1 = Category.objects.create(
            name="Category 1",
            slug="category-1",
        )

        category_2 = Category.objects.create(
            name="Category 2",
            slug="category-2",
        )

        Product.objects.create(
            name="Product 1",
            slug="product-1",
            brand=brand,
            category=category_1,
            manufacturer_article="ART-001",
            base_price=100,
        )

        Product.objects.create(
            name="Product 2",
            slug="product-2",
            brand=brand,
            category=category_2,
            manufacturer_article="ART-002",
            base_price=100,
        )

        response = self.client.get(
            reverse("api-product-list"),
            {
                "category": "category-1",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 1)

        self.assertEqual(response.data[0]["slug"], "product-1")

    # Проверяем, что фильтр по родительской категории
    # включает товары из дочерних категорий.
    def test_product_list_filter_by_parent_category_includes_child_products(self):
        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        parent_category = Category.objects.create(
            name="Cable",
            slug="cable",
        )

        child_category = Category.objects.create(
            name="Power cable",
            slug="power-cable",
            parent=parent_category,
        )

        Product.objects.create(
            name="Power Cable Product",
            slug="power-cable-product",
            brand=brand,
            category=child_category,
            manufacturer_article="CABLE-001",
            base_price=100,
        )

        response = self.client.get(
            reverse("api-product-list"),
            {
                "category": "cable",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "power-cable-product")

    # Проверяем, что обычный client не получает manager-only данные
    # в detail endpoint товара.
    def test_product_detail_does_not_return_manager_data_for_client(self):
        user = User.objects.create_user(
            email="client@test.com",
            username="client",
            password="12345678",
            role="client",
        )

        self.client.force_authenticate(user=user)

        brand = Brand.objects.create(
            name="Test brand",
            slug="test-brand",
        )

        category = Category.objects.create(
            name="Test category",
            slug="test-category",
        )

        product = Product.objects.create(
            name="Test product",
            slug="test-product",
            brand=brand,
            category=category,
            base_price=100,
        )

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("supplier_inventory_details", response.data)
        self.assertNotIn("cost_summary", response.data)

    def test_product_detail_returns_variants(self):
        from shop_epower.catalog.models import ProductVariantGroup

        # создаём 2 товара
        product1 = Product.objects.create(
            name="Variant Test White",
            slug="variant-test-white",
            base_price=100,
            brand=self.brand,
            category=self.category,
            manufacturer_article="VAR-001-WH",
        )

        product2 = Product.objects.create(
            name="Variant Test Black",
            slug="variant-test-black",
            base_price=100,
            brand=self.brand,
            category=self.category,
            manufacturer_article="VAR-001-BL",
        )

        # создаём группу вариантов
        group = ProductVariantGroup.objects.create(
            name="Variant Test Group",
            variant_type="color",
        )

        group.products.set([product1, product2])

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product1.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("variants", response.data)
        self.assertEqual(len(response.data["variants"]), 1)

        variant = response.data["variants"][0]

        self.assertEqual(variant["slug"], product2.slug)
        self.assertEqual(variant["variant_type"], "color")

    def test_product_detail_returns_variants(self):
        from shop_epower.catalog.models import ProductVariantGroup

        brand = Brand.objects.create(
            name="Variant brand",
            slug="variant-brand",
        )

        category = Category.objects.create(
            name="Variant category",
            slug="variant-category",
        )

        product1 = Product.objects.create(
            name="Variant Test White",
            slug="variant-test-white",
            base_price=100,
            brand=brand,
            category=category,
            manufacturer_article="VAR-001-WH",
        )

        product2 = Product.objects.create(
            name="Variant Test Black",
            slug="variant-test-black",
            base_price=100,
            brand=brand,
            category=category,
            manufacturer_article="VAR-001-BL",
        )

        group = ProductVariantGroup.objects.create(
            name="Variant Test Group",
            variant_type="color",
        )

        group.products.set([product1, product2])

        response = self.client.get(
            reverse(
                "api-product-detail",
                kwargs={"slug": product1.slug},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("variants", response.data)

        self.assertEqual(
            len(response.data["variants"]),
            1,
        )

        variant = response.data["variants"][0]

        self.assertEqual(
            variant["slug"],
            product2.slug,
        )

        self.assertEqual(
            variant["variant_type"],
            "color",
        )