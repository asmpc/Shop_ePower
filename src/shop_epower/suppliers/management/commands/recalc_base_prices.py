from django.core.management.base import BaseCommand
from shop_epower.catalog.models import Product
from shop_epower.suppliers.services.pricing import recalc_product_base_price

class Command(BaseCommand):
    help = "Recalculate base_price for all products based on supplier prices and global markup"

    def handle(self, *args, **options):
        products = Product.objects.all()
        total = products.count()
        self.stdout.write(f"Recalculating base_price for {total} products...")

        for i, product in enumerate(products, start=1):
            recalc_product_base_price(product)
            self.stdout.write(f"[{i}/{total}] Updated {product.name}: {product.base_price}")

        self.stdout.write(self.style.SUCCESS("Base price recalculation completed."))