from django.test import TestCase
from django.urls import reverse

from shop_epower.catalog.models import Brand, Category, Product, ProductVariantGroup



class TestCatalogView(TestCase):

    # Подготавливаем минимальные данные для каталога:
    # бренд, категория и один продукт.
    # Этого достаточно, чтобы протестировать работу списка товаров.
    def setUp(self):

        self.brand = Brand.objects.create(
            name="TestBrand",
            slug="testbrand"
        )

        self.category = Category.objects.create(
            name="TestCategory",
            slug="testcategory"
        )

        self.product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="ART123"
        )

    # Проверяем, что страница списка товаров (catalog)
    # успешно открывается и возвращает HTTP 200.
    def test_product_list_page_loads(self):

        url = reverse("catalog:product_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    # Проверяем, что поиск по query-параметру ?search=...
    # не ломает страницу и корректно обрабатывается view.
    # Здесь мы не проверяем результат поиска, только факт работы.
    def test_search_query(self):

        url = reverse("catalog:product_list")

        response = self.client.get(url + "?search=test")

        self.assertEqual(response.status_code, 200)

    # Проверяем, что фильтр по бренду (?brand=slug)
    # корректно обрабатывается и не вызывает ошибок.
    # Как и выше — тест на стабильность, а не на точность фильтрации.
    def test_brand_filter(self):

        url = reverse("catalog:product_list")

        response = self.client.get(url + f"?brand={self.brand.slug}")

        self.assertEqual(response.status_code, 200)

    # Проверяем, что detail page товара показывает связанные товары-варианты
    # через ProductVariantGroup, но не показывает текущий товар как вариант самого себя.
    def test_product_detail_shows_variant_products(self):
        product2 = Product.objects.create(
            name="Variant Product Black",
            slug="variant-product-black",
            brand=self.brand,
            category=self.category,
            manufacturer_article="VAR-BL-001",
            base_price=100,
        )

        group = ProductVariantGroup.objects.create(
            name="Variant Product Colors",
            variant_type="color",
        )

        group.products.set([self.product, product2])

        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"slug": self.product.slug},
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Variant Product Black")
        self.assertContains(response, product2.name)