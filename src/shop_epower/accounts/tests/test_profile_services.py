from django.contrib.auth import get_user_model
from django.test import TestCase

from shop_epower.accounts.models import LegalProfile
from shop_epower.accounts.services.profile import (
    is_profile_complete,
)


User = get_user_model()


class TestsProfileCompletenessService(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='user@test.com',
            username='user',
            password='strongpassword123',
            first_name='John',
            last_name='Doe',
            phone='+375291112233',
        )

    # Проверяем, что профиль физического лица
    # считается заполненным при наличии обязательных данных.
    def test_individual_profile_is_complete(self):

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=False,
        )

        self.assertTrue(
            is_profile_complete(self.user)
        )

    # Проверяем, что профиль физического лица
    # считается неполным без телефона.
    def test_individual_profile_without_phone_is_incomplete(self):

        self.user.phone = ''
        self.user.save(update_fields=['phone'])

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=False,
        )

        self.assertFalse(
            is_profile_complete(self.user)
        )

    # Проверяем, что профиль юридического лица
    # считается заполненным при наличии всех реквизитов.
    def test_legal_entity_profile_is_complete(self):

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name='Test Company',
            tax_id='123456789',
            legal_address='Minsk',
            bank_name='Test Bank',
            bank_account='BY00TEST123456789',
        )

        self.assertTrue(
            is_profile_complete(self.user)
        )

    # Проверяем, что профиль юридического лица
    # считается неполным без обязательного реквизита.
    def test_legal_entity_profile_without_tax_id_is_incomplete(self):

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name='Test Company',
            tax_id='',
            legal_address='Minsk',
            bank_name='Test Bank',
            bank_account='BY00TEST123456789',
        )

        self.assertFalse(
            is_profile_complete(self.user)
        )

    # Проверяем, что физическое лицо
    # может иметь полный профиль без LegalProfile.
    def test_profile_without_legal_profile_is_complete(self):
        self.assertTrue(
            is_profile_complete(self.user)
        )

    # Проверяем, что отсутствие имени
    # делает профиль неполным.
    def test_profile_without_first_name_is_incomplete(self):
        self.user.first_name = ''
        self.user.save(update_fields=['first_name'])

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=False,
        )

        self.assertFalse(
            is_profile_complete(self.user)
        )

    # Проверяем, что отсутствие фамилии
    # делает профиль неполным.
    def test_profile_without_last_name_is_incomplete(self):
        self.user.last_name = ''
        self.user.save(update_fields=['last_name'])

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=False,
        )

        self.assertFalse(
            is_profile_complete(self.user)
        )

    # Проверяем, что имя, состоящее только из пробелов,
    # делает профиль физического лица неполным.
    def test_profile_with_blank_first_name_is_incomplete(self):

        self.user.first_name = '   '
        self.user.save(update_fields=['first_name'])

        self.assertFalse(
            is_profile_complete(self.user)
        )

    # Проверяем, что название компании из одних пробелов
    # делает профиль юридического лица неполным.
    def test_legal_entity_with_blank_company_name_is_incomplete(self):

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name='   ',
            tax_id='123456789',
            legal_address='Minsk',
            bank_name='Test Bank',
            bank_account='BY00TEST123456789',
        )

        self.assertFalse(
            is_profile_complete(self.user)
        )
