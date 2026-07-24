from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import create_test_user


class TestsLoginWorkflow(TestCase):

    # Проверяем, что ссылка на регистрацию
    # сохраняет маршрут возврата.
    def test_register_link_preserves_next_url(self):

        next_url = reverse(
            "cart-detail",
        )

        response = self.client.get(
            reverse(
                "accounts:login",
            ),
            {
                "next": next_url,
            },
        )

        expected_register_url = (
            f"{reverse('accounts:register')}"
            f"?next={next_url}"
        )

        self.assertContains(
            response,
            f'href="{expected_register_url}"',
        )

    # Проверяем, что форма входа
    # сохраняет маршрут возврата.
    def test_login_form_contains_next_field(self):
        next_url = reverse(
            "cart-detail",
        )

        response = self.client.get(
            reverse(
                "accounts:login",
            ),
            {
                "next": next_url,
            },
        )

        self.assertContains(
            response,
            (
                f'<input type="hidden" '
                f'name="next" '
                f'value="{next_url}"'
            ),
            html=True,
        )

    # Проверяем, что после успешного входа
    # пользователь возвращается по next.
    def test_login_redirects_to_next_url(self):
        password = "StrongPassword123"

        create_test_user(
            email="user@test.com",
            username="testuser",
            password=password,
        )

        next_url = reverse(
            "cart-detail",
        )

        response = self.client.post(
            reverse(
                "accounts:login",
            ),
            data={
                "username": "user@test.com",
                "password": password,
                "next": next_url,
            },
        )

        self.assertRedirects(
            response,
            next_url,
        )