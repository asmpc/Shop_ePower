from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.models import User


class TestsRegisterWorkflow(TestCase):

    # Проверяем, что после регистрации
    # сохраняется маршрут возврата.
    def test_register_preserves_next_url(self):

        next_url = reverse(
            "cart-detail",
        )

        response = self.client.post(
            reverse(
                "accounts:register",
            ) + f"?next={next_url}",
            data={
                "email": "user@test.com",
                "username": "testuser",
                "password1": "StrongPassword123",
                "password2": "StrongPassword123",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_edit",
            ) + f"?next={next_url}",
        )

        self.assertTrue(
            User.objects.filter(
                email="user@test.com",
            ).exists()
        )

    # Проверяем, что внешний адрес
    # не используется для перенаправления.
    def test_register_ignores_unsafe_next_url(self):
        response = self.client.post(
            reverse(
                "accounts:register",
            ) + "?next=https://example.com/unsafe/",
            data={
                "email": "user@test.com",
                "username": "testuser",
                "password1": "StrongPassword123",
                "password2": "StrongPassword123",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "accounts:profile_edit",
            ),
        )

