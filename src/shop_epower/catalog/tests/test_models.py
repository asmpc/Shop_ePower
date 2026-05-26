from django.test import TestCase

from shop_epower.catalog.models import Brand, Category, Product, ProductVariantGroup



class TestProductModel(TestCase):

    # Создаём общие Brand и Category, которые нужны всем тестам Product.
    def setUp(self):

        self.brand = Brand.objects.create(name="TestBrand")
        self.category = Category.objects.create(name="TestCategory")

    # Проверяем, что нельзя создать два товара с одинаковым manufacturer_article
    # внутри одного бренда.
    # Это защищает каталог от дублей: артикул производителя должен быть уникален
    # в рамках конкретного бренда.
    def test_unique_brand_article_constraint(self):

        Product.objects.create(
            name="Product 1",
            brand=self.brand,
            category=self.category,
            manufacturer_article="ABC123"
        )

        with self.assertRaises(Exception):

            Product.objects.create(
                name="Product 2",
                brand=self.brand,
                category=self.category,
                manufacturer_article="ABC123"
            )

    # Проверяем, что slug для товара создаётся автоматически при сохранении.
    # Slug нужен для человекочитаемых URL, например /products/test-product/.
    def test_slug_generated(self):

        product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="XYZ"
        )

        self.assertIsNotNone(product.slug)


class ProductVariantGroupModelTestCase(TestCase):

    # Проверяем, что ProductVariantGroup связывает несколько самостоятельных Product
    # как варианты друг друга, например разные цвета одного товара.
    def test_product_variant_group_contains_products(self):
        brand = Brand.objects.create(
            name="Variant Brand",
            slug="variant-brand",
        )

        category = Category.objects.create(
            name="Variant Category",
            slug="variant-category",
        )

        product1 = Product.objects.create(
            name="Variant Product White",
            slug="variant-product-white",
            brand=brand,
            category=category,
            manufacturer_article="VAR-WH-001",
            base_price=100,
        )

        product2 = Product.objects.create(
            name="Variant Product Black",
            slug="variant-product-black",
            brand=brand,
            category=category,
            manufacturer_article="VAR-BL-001",
            base_price=100,
        )

        group = ProductVariantGroup.objects.create(
            name="Variant Product Colors",
            variant_type="color",
        )

        group.products.set([product1, product2])

        self.assertEqual(group.products.count(), 2)
        self.assertIn(product1, group.products.all())
        self.assertIn(product2, group.products.all())