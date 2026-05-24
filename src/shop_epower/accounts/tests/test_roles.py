from django.test import TestCase

from shop_epower.accounts.models import User, Role
from shop_epower.accounts.services.roles import (
    is_admin,
    is_client,
    is_manager,
)


class RoleServiceTestCase(TestCase):
    def test_anonymous_user_is_client_not_manager(self):
        class AnonymousUser:
            is_authenticated = False

        user = AnonymousUser()

        self.assertTrue(is_client(user))
        self.assertFalse(is_manager(user))
        self.assertFalse(is_admin(user))

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