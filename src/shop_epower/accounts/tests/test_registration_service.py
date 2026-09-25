from unittest.mock import patch

from django.test import TestCase

from shop_epower.accounts.models import User
from shop_epower.accounts.services import register_customer
from shop_epower.finance.models import CustomerAccount, CustomerAccountType


class TestsCustomerRegistrationService(TestCase):
    # Регистрация создаёт пользователя и ровно один личный финансовый счёт.
    def test_register_customer_creates_user_and_personal_account(self):
        user = register_customer(
            email="new-client@example.com",
            username="new-client",
            password="testpass123",
        )

        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(user.check_password("testpass123"))
        self.assertEqual(CustomerAccount.objects.count(), 1)

        account = CustomerAccount.objects.get(user=user)
        self.assertEqual(account.account_type, CustomerAccountType.PERSONAL)

    # Ошибка создания счёта откатывает всю регистрацию, включая пользователя.
    def test_register_customer_rolls_back_user_when_account_creation_fails(self):
        with patch(
            "shop_epower.accounts.services.registration.create_personal_customer_account",
            side_effect=RuntimeError("Account creation failed."),
        ):
            with self.assertRaisesMessage(RuntimeError, "Account creation failed."):
                register_customer(
                    email="rollback@example.com",
                    username="rollback",
                    password="testpass123",
                )

        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(CustomerAccount.objects.count(), 0)
