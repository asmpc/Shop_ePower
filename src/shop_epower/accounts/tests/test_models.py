from django.test import TestCase

from shop_epower.accounts.models import (
    User,
    Role,
    PriceCategory,
)


class TestsRoleModel(TestCase):

    def test_user_default_role(self):

        user = User.objects.create_user(
            email='test@test.com',
            username='testuser',
            password='strongpassword123',
        )

        self.assertEqual(
            user.role,
            Role.CLIENT
        )

    def test_user_can_have_manager_role(self):

        user = User.objects.create_user(
            email='manager@test.com',
            username='manager',
            password='strongpassword123',
            role=Role.MANAGER,
        )

        self.assertEqual(
            user.role,
            Role.MANAGER
        )

    def test_user_can_have_admin_role(self):

        user = User.objects.create_user(
            email='admin@test.com',
            username='admin',
            password='strongpassword123',
            role=Role.ADMIN,
        )

        self.assertEqual(
            user.role,
            Role.ADMIN
        )


class PriceCategoryTests(TestCase):

    def setUp(self):

        self.price_category = PriceCategory.objects.create(
            name='Dealer',
            discount_percent=10,
        )

    def test_price_category_created(self):

        self.assertEqual(
            self.price_category.name,
            'Dealer'
        )

        self.assertEqual(
            self.price_category.discount_percent,
            10
        )

    def test_price_category_str_method(self):

        self.assertEqual(
            str(self.price_category),
            'Dealer (10%)'
        )

    def test_user_can_have_price_category(self):

        user = User.objects.create_user(
            email='dealer@test.com',
            username='dealer',
            password='strongpassword123',
            price_category=self.price_category,
        )

        self.assertEqual(
            user.price_category,
            self.price_category
        )