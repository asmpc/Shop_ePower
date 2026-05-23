from django.test import TestCase
from shop_epower.catalog.models import Brand, Product, Category


class TestProductModel(TestCase):

    def setUp(self):

        self.brand = Brand.objects.create(name="TestBrand")
        self.category = Category.objects.create(name="TestCategory")

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


    def test_slug_generated(self):

        product = Product.objects.create(
            name="Test Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="XYZ"
        )

        self.assertIsNotNone(product.slug)