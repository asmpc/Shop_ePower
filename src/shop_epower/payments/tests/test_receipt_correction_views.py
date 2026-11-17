from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.services import assign_order_funds
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import record_manual_account_payment
from shop_epower.payments.tests.helpers import create_test_payment


class TestsManagerReceiptCorrectionViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="receipt:correction-view:original",
            created_by=self.manager,
        )

        self.url = reverse(
            "payments:manager_cancel_receipt",
            kwargs={"pk": self.payment.pk},
        )

    # Менеджер открывает форму отмены поступления без заказа.
    # Форма требует причину и содержит ключ операции и CSRF.
    # Просмотр не меняет платёж, баланс или историю.
    def test_manager_can_open_receipt_cancellation_form(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "payments/manage/receipt_cancellation_form.html",
        )
        self.assertEqual(
            response.context["payment"].pk,
            self.payment.pk,
        )
        self.assertContains(response, self.user.email)
        self.assertContains(response, 'name="comment"')
        self.assertContains(response, 'name="operation_key"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        form = response.context["form"]

        self.assertTrue(form.fields["comment"].required)
        self.assertTrue(form.initial.get("operation_key"))

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Подтверждение отмены вызывает сторнирование поступления.
    # Причина и сотрудник сохраняются в истории,
    # после успеха открывается карточка платежа.
    def test_manager_can_confirm_receipt_cancellation(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        reason = "Money was not actually received."

        response = self.client.post(
            self.url,
            {
                "comment": reason,
                "operation_key": operation_key,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "payments:manager_payment_detail",
                kwargs={"pk": self.payment.pk},
            ),
        )

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertTrue(
            self.account.transactions.filter(
                reversal_of_id=self.payment.deposit_transaction_id,
            ).exists(),
        )

        history = self.payment.history.get()

        self.assertEqual(history.old_status, PaymentStatus.PAID)
        self.assertEqual(history.new_status, PaymentStatus.CANCELLED)
        self.assertEqual(history.comment, reason)
        self.assertEqual(history.changed_by_id, self.manager.pk)

    # Карточка поступления содержит ссылку на форму отмены.
    # Ссылка передаёт полный адрес платежа с исходными фильтрами.
    def test_payment_detail_links_to_receipt_cancellation_form(self):
        list_url = (
            reverse("payments:manager_payment_list")
            + "?"
            + urlencode(
                {
                    "customer_email": self.user.email,
                    "status": "paid",
                    "page": 1,
                }
            )
        )
        payment_url = (
            reverse(
                "payments:manager_payment_detail",
                kwargs={"pk": self.payment.pk},
            )
            + "?"
            + urlencode({"next": list_url})
        )
        cancellation_url = (
            self.url
            + "?"
            + urlencode({"next": payment_url})
        )

        self.client.force_login(self.manager)

        response = self.client.get(payment_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{escape(cancellation_url)}"',
        )
        self.assertContains(response, "Cancel receipt")

        form_response = self.client.get(cancellation_url)

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(
            form_response.context["return_url"],
            payment_url,
        )
        self.assertContains(
            form_response,
            f'href="{escape(payment_url)}"',
        )
        self.assertContains(
            form_response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(payment_url)}">'
            ),
            html=True,
        )

    # После отмены открывается карточка платежа с исходным контекстом.
    # Её кнопка Back сохраняет фильтры списка Payments.
    def test_receipt_cancellation_preserves_payment_return_context(self):
        list_url = (
            reverse("payments:manager_payment_list")
            + "?"
            + urlencode(
                {
                    "customer_email": self.user.email,
                    "status": "paid",
                    "page": 1,
                }
            )
        )
        payment_url = (
            reverse(
                "payments:manager_payment_detail",
                kwargs={"pk": self.payment.pk},
            )
            + "?"
            + urlencode({"next": list_url})
        )

        self.client.force_login(self.manager)

        form_response = self.client.get(
            self.url,
            {"next": payment_url},
        )
        self.assertEqual(form_response.status_code, 200)

        response = self.client.post(
            self.url,
            {
                "comment": "Money was not actually received.",
                "operation_key": (
                    form_response.context["form"]
                    .initial["operation_key"]
                ),
                "next": form_response.context["return_url"],
            },
            follow=True,
        )

        self.assertRedirects(response, payment_url)
        self.assertEqual(
            response.context["back_url"],
            list_url,
        )

    # Пустая причина и пробелы отклоняются сервером.
    # Форма сохраняет ключ операции, деньги и история не меняются.
    def test_cancellation_requires_nonblank_reason(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )

        for reason in ("", "   "):
            with self.subTest(reason=reason):
                response = self.client.post(
                    self.url,
                    {
                        "comment": reason,
                        "operation_key": operation_key,
                    },
                )

                self.assertEqual(response.status_code, 200)

                form = response.context["form"]

                self.assertIn("comment", form.errors)
                self.assertEqual(
                    form["operation_key"].value(),
                    operation_key,
                )

                self.payment.refresh_from_db()
                self.account.refresh_from_db()

                self.assertEqual(
                    self.payment.status,
                    PaymentStatus.PAID,
                )
                self.assertEqual(
                    self.account.available_balance,
                    Decimal("100.00"),
                )
                self.assertEqual(
                    self.account.debt_balance,
                    Decimal("0.00"),
                )
                self.assertEqual(self.account.transactions.count(), 1)
                self.assertEqual(self.payment.history.count(), 0)

    # Использованные деньги нельзя отменить через форму.
    # Ошибка сервиса показывается без потери введённой причины и ключа.
    def test_active_assignment_error_is_shown_without_cancelling_receipt(self):
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )
        assign_order_funds(
            order=order,
            amount=Decimal("60.00"),
            operation_key="receipt:correction-view:active-assignment",
            created_by=self.manager,
        )

        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        operation_key = (
            form_response.context["form"].initial["operation_key"]
        )
        reason = "Receipt registered by mistake."

        response = self.client.post(
            self.url,
            {
                "comment": reason,
                "operation_key": operation_key,
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertIn(
            "Cancel dependent fund assignments before cancelling the receipt.",
            form.non_field_errors(),
        )
        self.assertEqual(form["comment"].value(), reason)
        self.assertEqual(
            form["operation_key"].value(),
            operation_key,
        )

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("40.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.payment.history.count(), 0)

    # Клиенту запрещены просмотр формы и прямой POST отмены.
    # Даже собственное поступление клиент не может отменить.
    def test_customer_cannot_open_or_submit_cancellation_form(self):
        self.client.force_login(self.user)

        form_response = self.client.get(self.url)

        self.assertEqual(form_response.status_code, 403)

        cancellation_response = self.client.post(
            self.url,
            {
                "comment": "Attempt by customer.",
                "operation_key": "receipt:correction-view:forbidden",
            },
        )

        self.assertEqual(cancellation_response.status_code, 403)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)
        self.assertEqual(self.payment.history.count(), 0)

    # Администратор отменяет выбранное банковское поступление.
    # Другое поступление на том же счёте остаётся действующим.
    def test_admin_can_cancel_selected_bank_receipt(self):
        admin = create_test_admin()

        bank_payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("60.00"),
            method=PaymentMethod.INVOICE,
            operation_key="receipt:correction-view:bank",
            created_by=self.manager,
        )
        cancellation_url = reverse(
            "payments:manager_cancel_receipt",
            kwargs={"pk": bank_payment.pk},
        )

        self.client.force_login(admin)

        form_response = self.client.get(cancellation_url)
        reason = "Bank receipt registered by mistake."

        response = self.client.post(
            cancellation_url,
            {
                "comment": reason,
                "operation_key": (
                    form_response.context["form"]
                    .initial["operation_key"]
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "payments:manager_payment_detail",
                kwargs={"pk": bank_payment.pk},
            ),
        )

        bank_payment.refresh_from_db()
        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(bank_payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(self.payment.history.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 3)

        history = bank_payment.history.get()

        self.assertEqual(history.comment, reason)
        self.assertEqual(history.changed_by_id, admin.pk)

    # Повтор одной формы не создаёт второе сторно или историю.
    # Оба запроса возвращают сотрудника к карточке платежа.
    def test_repeated_submission_does_not_reverse_receipt_twice(self):
        self.client.force_login(self.manager)

        form_response = self.client.get(self.url)
        cancellation_data = {
            "comment": "Receipt registered by mistake.",
            "operation_key": (
                form_response.context["form"].initial["operation_key"]
            ),
        }
        payment_url = reverse(
            "payments:manager_payment_detail",
            kwargs={"pk": self.payment.pk},
        )

        first_response = self.client.post(
            self.url,
            cancellation_data,
        )
        repeated_response = self.client.post(
            self.url,
            cancellation_data,
        )

        self.assertRedirects(first_response, payment_url)
        self.assertRedirects(repeated_response, payment_url)

        self.payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.account.transactions.count(), 2)
        self.assertEqual(self.payment.history.count(), 1)

    # Внешний адрес возврата заменяется карточкой текущего платежа.
    # Проверка действует при открытии формы и после подтверждения.
    def test_external_return_url_is_replaced_with_payment_url(self):
        payment_url = reverse(
            "payments:manager_payment_detail",
            kwargs={"pk": self.payment.pk},
        )
        external_url = "https://example.org/"

        self.client.force_login(self.manager)

        form_response = self.client.get(
            self.url,
            {"next": external_url},
        )

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(
            form_response.context["return_url"],
            payment_url,
        )

        response = self.client.post(
            self.url,
            {
                "comment": "Receipt registered by mistake.",
                "operation_key": (
                    form_response.context["form"]
                    .initial["operation_key"]
                ),
                "next": external_url,
            },
        )

        self.assertRedirects(response, payment_url)

    # Старый PAID-платёж без пополнения не предлагает отмену поступления.
    # Прямые GET и POST формы также недоступны.
    def test_legacy_payment_without_deposit_cannot_be_cancelled(self):
        legacy_order = create_test_order(
            user=self.user,
            customer_account=self.account,
        )
        legacy_payment = create_test_payment(
            order=legacy_order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            provider=PaymentProvider.MANUAL,
            status=PaymentStatus.PAID,
            currency_snapshot=self.account.currency,
        )
        cancellation_url = reverse(
            "payments:manager_cancel_receipt",
            kwargs={"pk": legacy_payment.pk},
        )

        self.client.force_login(self.manager)

        detail_response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                kwargs={"pk": legacy_payment.pk},
            ),
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(detail_response, "Cancel receipt")

        form_response = self.client.get(cancellation_url)
        self.assertEqual(form_response.status_code, 404)

        cancellation_response = self.client.post(
            cancellation_url,
            {
                "comment": "Attempt to cancel a legacy payment.",
                "operation_key": "receipt:correction-view:legacy",
            },
        )
        self.assertEqual(cancellation_response.status_code, 404)

        legacy_payment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(legacy_payment.status, PaymentStatus.PAID)
        self.assertEqual(legacy_payment.history.count(), 0)
        self.assertEqual(
            self.account.available_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)

    # Карточка показывает автора регистрации поступления.
    # Просматривающий сотрудник может отличаться от автора.
    def test_payment_detail_shows_original_receipt_author(self):
        viewer = create_test_manager()
        self.client.force_login(viewer)

        response = self.client.get(
            reverse(
                "payments:manager_payment_detail",
                kwargs={"pk": self.payment.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"""
            <p class="mb-1">
                <strong>Registered by:</strong>
                {escape(self.manager.username)}
            </p>
            """,
            html=True,
        )

    # После отмены сохраняется автор регистрации поступления.
    # В истории отдельно показывается менеджер, выполнивший отмену.
    def test_cancellation_preserves_original_author_and_shows_canceller(self):
        canceller = create_test_manager()
        self.client.force_login(canceller)

        form_response = self.client.get(self.url)

        response = self.client.post(
            self.url,
            {
                "comment": "Receipt registered by mistake.",
                "operation_key": (
                    form_response.context["form"]
                    .initial["operation_key"]
                ),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["payment"].status,
            PaymentStatus.CANCELLED,
        )
        self.assertContains(
            response,
            f"""
            <p class="mb-1">
                <strong>Registered by:</strong>
                {escape(self.manager.username)}
            </p>
            """,
            html=True,
        )
        self.assertContains(
            response,
            f"""
            <p class="mb-1">
                <strong>Changed by:</strong>
                {escape(canceller.username)}
            </p>
            """,
            html=True,
        )
