from django.test import TestCase

from shop_epower.accounts.models import (
    User,
    Role,
    PriceCategory,
)


class TestsRoleModel(TestCase):

    # Проверяем, что при создании пользователя без указания роли
    # ему автоматически присваивается роль CLIENT по умолчанию.
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

    # Проверяем, что пользователю можно явно задать роль MANAGER
    # при создании аккаунта.
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

    # Проверяем, что пользователю можно явно задать роль ADMIN
    # при создании аккаунта.
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

    # Подготавливаем тестовую категорию цен (скидку),
    # которая будет использоваться в тестах.
    def setUp(self):

        self.price_category = PriceCategory.objects.create(
            name='Dealer',
            discount_percent=10,
        )

    # Проверяем, что PriceCategory корректно создаётся
    # и сохраняет заданные значения.
    def test_price_category_created(self):

        self.assertEqual(
            self.price_category.name,
            'Dealer'
        )

        self.assertEqual(
            self.price_category.discount_percent,
            10
        )

    # Проверяем строковое представление PriceCategory,
    # которое используется в admin и интерфейсе.
    def test_price_category_str_method(self):

        self.assertEqual(
            str(self.price_category),
            'Dealer (10%)'
        )

    # Проверяем, что пользователю можно назначить PriceCategory,
    # и связь сохраняется корректно.
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

    # Проверяем, что у пользователя без явно заданной PriceCategory
    # значение price_category равно None.
    def test_user_without_price_category(self):
        user = User.objects.create_user(
            email='no_category@test.com',
            username='no_category',
            password='strongpassword123',
        )

        self.assertIsNone(user.price_category)