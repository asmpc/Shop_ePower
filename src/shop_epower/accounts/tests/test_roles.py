from django.test import TestCase

from shop_epower.accounts.models import User, Role
from shop_epower.accounts.services.roles import (
    is_admin,
    is_client,
    is_manager,
)


class TestsRoleService(TestCase):

    # Проверяем поведение для неавторизованного пользователя:
    # - считается клиентом (базовый доступ)
    # - не имеет прав менеджера или администратора
    def test_anonymous_user_is_client_not_manager(self):
        class AnonymousUser:
            is_authenticated = False

        user = AnonymousUser()

        self.assertTrue(is_client(user))
        self.assertFalse(is_manager(user))
        self.assertFalse(is_admin(user))

    # Проверяем пользователя с ролью CLIENT:
    # - имеет клиентские права
    # - не является менеджером или администратором
    def test_client_role(self):
        user = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="testpass123",
            role=Role.CLIENT,
        )

        self.assertTrue(is_client(user))
        self.assertFalse(is_manager(user))
        self.assertFalse(is_admin(user))

    # Проверяем пользователя с ролью MANAGER:
    # - имеет права менеджера
    # - не является администратором
    # - не считается клиентом
    def test_manager_role(self):
        user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123",
            role=Role.MANAGER,
        )

        self.assertFalse(is_client(user))
        self.assertTrue(is_manager(user))
        self.assertFalse(is_admin(user))

    # Проверяем пользователя с ролью ADMIN:
    # - имеет права администратора
    # - автоматически считается менеджером (расширенные права)
    # - не считается клиентом
    def test_admin_role(self):
        user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role=Role.ADMIN,
        )

        self.assertFalse(is_client(user))
        self.assertTrue(is_manager(user))
        self.assertTrue(is_admin(user))

    # Проверяем, что неавторизованный пользователь
    # не является администратором.
    def test_anonymous_user_is_not_admin(self):
        class AnonymousUser:
            is_authenticated = False

        user = AnonymousUser()

        self.assertFalse(is_admin(user))