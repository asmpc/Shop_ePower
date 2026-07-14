from django.test import TestCase

from shop_epower.payments.models import CompanySettings


class TestsCompanySettingsModel(TestCase):

    def setUp(self):
        self.company_settings = CompanySettings.objects.create(
            company_name="Shop ePower LLC",
            short_company_name="Shop ePower",

            tax_id="123456789",
            tax_registration_reason_code="290101001",
            state_registration_number="1152901008622",

            legal_address="Test legal address",
            actual_address="Test actual address",

            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
            bank_code="TESTBY22",
            correspondent_account="30101810100000000601",

            phone="+375291112233",
            email="info@shop-epower.test",
        )

    # Проверяем основные реквизиты компании:
    # название, налоговый номер и адрес должны сохраняться.
    def test_company_settings_stores_main_company_data(self):
        self.assertEqual(
            self.company_settings.company_name,
            "Shop ePower LLC",
        )

        self.assertEqual(
            self.company_settings.short_company_name,
            "Shop ePower",
        )

        self.assertEqual(
            self.company_settings.tax_id,
            "123456789",
        )

        self.assertEqual(
            self.company_settings.legal_address,
            "Test legal address",
        )

        self.assertEqual(
            self.company_settings.actual_address,
            "Test actual address",
        )

    # Проверяем дополнительные регистрационные данные:
    # КПП и ОГРН нужны для российских реквизитов,
    # но могут оставаться пустыми для Беларуси.
    def test_company_settings_stores_registration_data(self):
        self.assertEqual(
            self.company_settings.tax_registration_reason_code,
            "290101001",
        )

        self.assertEqual(
            self.company_settings.state_registration_number,
            "1152901008622",
        )

    # Проверяем банковские реквизиты:
    # расчетный счет, БИК и корреспондентский счет
    # должны сохраняться для будущих invoice PDF.
    def test_company_settings_stores_bank_data(self):
        self.assertEqual(
            self.company_settings.bank_name,
            "Test Bank",
        )

        self.assertEqual(
            self.company_settings.bank_account,
            "BY00 TEST 0000 0000 0000 0000 0000",
        )

        self.assertEqual(
            self.company_settings.bank_code,
            "TESTBY22",
        )

        self.assertEqual(
            self.company_settings.correspondent_account,
            "30101810100000000601",
        )

    # Проверяем контактные данные компании:
    # телефон и email должны быть доступны для счетов и документов.
    def test_company_settings_stores_contact_data(self):
        self.assertEqual(
            self.company_settings.phone,
            "+375291112233",
        )

        self.assertEqual(
            self.company_settings.email,
            "info@shop-epower.test",
        )

    # Проверяем строковое представление:
    # в админке и логах должно отображаться название компании.
    def test_company_settings_str(self):
        self.assertEqual(
            str(self.company_settings),
            "Shop ePower LLC",
        )