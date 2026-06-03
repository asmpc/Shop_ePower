from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop_epower.orders.models import Order, OrderStatus, OrderItem
from shop_epower.catalog.models import Brand, Category, Product


User = get_user_model()


class TestsManagerOrderViews(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            email="frontend-manager@example.com",
            username="frontend-manager",
            password="testpass123",
            role="manager",
        )

        self.client_user = User.objects.create_user(
            email="frontend-client@example.com",
            username="frontend-client",
            password="testpass123",
            role="client",
        )

        self.order = Order.objects.create(
            user=self.client_user,
            status=OrderStatus.PROCESSING,
            is_legal_entity=False,
            customer_name="Frontend Client",
            customer_email="frontend-client@example.com",
            customer_phone="+10000000040",
            total_price=Decimal("100.00"),
            delivery_method="shipping",
            delivery_provider="post",
            delivery_address="Frontend address",
            delivery_comment="Frontend comment",
        )

        self.brand = Brand.objects.create(
            name="Frontend Delivery Brand",
        )

        self.category = Category.objects.create(
            name="Frontend Delivery Category",
        )

        self.product = Product.objects.create(
            name="Frontend Delivery Product",
            brand=self.brand,
            category=self.category,
            manufacturer_article="FRONTEND-DELIVERY-001",
            base_price=Decimal("100.00"),
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    # Проверяем manager detail page:
    # для заказа в статусе PROCESSING
    # отображаются кнопки Complete order и Cancel order.
    def test_manager_detail_page_shows_cancel_button_for_processing_order(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete order")
        self.assertContains(response, "Cancel order")

    # Проверяем manager frontend workflow:
    # менеджер может отменить заказ
    # в статусе PROCESSING через frontend form.
    def test_manager_can_cancel_processing_order_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_status_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "status": OrderStatus.CANCELLED,
                "cancellation_reason": "client_refused",
                "cancellation_comment": "Client changed their mind.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.CANCELLED,
        )
        self.assertEqual(
            self.order.cancellation_reason,
            "client_refused",
        )

        self.assertEqual(
            self.order.cancellation_comment,
            "Client changed their mind.",
        )

    # Проверяем отображение cancellation info:
    # после отмены заказа manager detail page
    # показывает причину и комментарий отмены.
    def test_manager_detail_page_shows_cancellation_info(self):
        self.order.status = OrderStatus.CANCELLED
        self.order.cancellation_reason = "delivery_cost"
        self.order.cancellation_comment = "Delivery price was too high."
        self.order.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancellation_comment",
            ]
        )

        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delivery cost")
        self.assertContains(response, "Delivery price was too high.")

    # Проверяем delivery display:
    # manager order detail page показывает delivery информацию.
    def test_manager_order_detail_page_shows_delivery_info(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shipping")
        self.assertContains(response, "Post")
        self.assertContains(response, "Frontend address")
        self.assertContains(response, "Frontend comment")

    # Проверяем manager delivery frontend pricing:
    # manager может обновить стоимость доставки через форму,
    # и delivery cost прибавляется к total_price.
    def test_manager_can_update_delivery_cost_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_delivery_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "delivery_cost": "25.00",
                "manager_delivery_comment": "Delivery included.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_cost,
            Decimal("25.00"),
        )

        self.assertEqual(
            self.order.total_price,
            Decimal("125.00"),
        )

    # Проверяем manager delivery frontend pricing:
    # если manager отмечает оплату доставки при получении,
    # delivery cost сохраняется, но total_price не меняется.
    def test_manager_can_mark_delivery_as_paid_on_receipt_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_delivery_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "delivery_cost": "25.00",
                "delivery_paid_by_customer_on_receipt": "on",
                "manager_delivery_comment": "Customer pays on receipt.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_cost,
            Decimal("25.00"),
        )

        self.assertEqual(
            self.order.total_price,
            Decimal("100.00"),
        )

        self.assertTrue(
            self.order.delivery_paid_by_customer_on_receipt,
        )