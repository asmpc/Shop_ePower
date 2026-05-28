from django.conf import settings
from django.db import models

from shop_epower.core.currency import get_base_currency


class OrderStatus(models.TextChoices):
    NEW = "new", "New"
    PROCESSING = "processing", "Processing"
    PAID = "paid", "Paid"
    SHIPPED = "shipped", "Shipped"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"

class OrderCancellationReason(models.TextChoices):
    CLIENT_REFUSED = "client_refused", "Client refused"

    SUPPLIER_UNAVAILABLE = "supplier_unavailable", "Supplier unavailable"

    DELIVERY_COST = "delivery_cost", "Delivery cost"

    OTHER = "other", "Other"

class DeliveryMethod(models.TextChoices):
    PICKUP = "pickup", "Pickup"

    SHIPPING = "shipping", "Shipping"

class DeliveryProvider(models.TextChoices):
    POST = "post", "Post"

    TRANSPORT_COMPANY = (
        "transport_company",
        "Transport company",
    )

    OTHER = "other", "Other"

class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.NEW,
    )

    cancellation_reason = models.CharField(
        max_length=50,
        choices=OrderCancellationReason.choices,
        blank=True,
    )

    cancellation_comment = models.TextField(
        blank=True,
    )

    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP,
    )

    delivery_provider = models.CharField(
        max_length=50,
        choices=DeliveryProvider.choices,
        blank=True,
    )

    delivery_address = models.TextField(
        blank=True,
        null=True,
    )

    delivery_comment = models.TextField(
        blank=True,
    )

    manager_delivery_comment = models.TextField(
        blank=True,
    )

    delivery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    delivery_paid_by_customer_on_receipt = models.BooleanField(
        default=False,
    )

    is_legal_entity = models.BooleanField(
        default=False,
    )

    customer_name = models.CharField(
        max_length=255,
    )

    customer_email = models.EmailField()

    customer_phone = models.CharField(
        max_length=30,
        blank=True,
    )

    delivery_address = models.TextField(
        blank=True,
        null=True,
    )

    company_name = models.CharField(
        max_length=255,
        blank=True,
    )

    tax_id = models.CharField(
        max_length=50,
        blank=True,
    )

    legal_address = models.TextField(
        blank=True,
    )

    bank_name = models.CharField(
        max_length=255,
        blank=True,
    )

    bank_account = models.CharField(
        max_length=100,
        blank=True,
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    currency_snapshot = models.CharField(
        max_length=10,
        default=get_base_currency,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} by {self.customer_email}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    product_name = models.CharField(
        max_length=255,
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    quantity = models.PositiveIntegerField()

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency_snapshot = models.CharField(
        max_length=10,
        default=get_base_currency,
    )

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class OrderStockReservation(models.Model):
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="stock_reservations",
    )

    supplier_product = models.ForeignKey(
        "suppliers.SupplierProduct",
        on_delete=models.PROTECT,
        related_name="order_stock_reservations",
    )

    quantity = models.PositiveIntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return (
            f"{self.order_item.product_name} "
            f"x {self.quantity}"
        )
