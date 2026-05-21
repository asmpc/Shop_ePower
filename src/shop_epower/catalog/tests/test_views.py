from django.test import TestCase
from django.urls import reverse

from shop_epower.catalog.models import Brand, Category, Product


class TestCatalogView(TestCase):

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

    def test_product_list_page_loads(self):

        url = reverse("catalog:product_list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_search_query(self):

        url = reverse("catalog:product_list")

        response = self.client.get(url + "?search=test")

        self.assertEqual(response.status_code, 200)

    def test_brand_filter(self):

        url = reverse("catalog:product_list")

        response = self.client.get(url + f"?brand={self.brand.slug}")

        self.assertEqual(response.status_code, 200)

    def test_variant_creation(self):

        product = self.product

        variant = product.variants.create(
            name="White",
            color="white"
        )

        self.assertEqual(variant.product, product)