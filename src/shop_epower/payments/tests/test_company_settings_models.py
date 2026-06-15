from django.test import TestCase

from shop_epower.payments.models import CompanySettings


class TestsCompanySettingsModel(TestCase):

    # Проверяем создание реквизитов компании:
    # эти данные будут использоваться как актуальные реквизиты
    # для новых счетов и документов.
    def test_create_company_settings(self):
        company_settings = CompanySettings.objects.create(
            company_name="Shop ePower LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
            bank_code="TESTBY22",
            phone="+375291112233",
            email="info@shop-epower.test",
        )

        self.assertEqual(
            company_settings.company_name,
            "Shop ePower LLC",
        )

        self.assertEqual(
            company_settings.tax_id,
            "123456789",
        )

        self.assertEqual(
            company_settings.legal_address,
            "Test legal address",
        )

        self.assertEqual(
            company_settings.bank_name,
            "Test Bank",
        )

        self.assertEqual(
            company_settings.bank_account,
            "BY00 TEST 0000 0000 0000 0000 0000",
        )

        self.assertEqual(
            company_settings.bank_code,
            "TESTBY22",
        )

        self.assertEqual(
            company_settings.phone,
            "+375291112233",
        )

        self.assertEqual(
            company_settings.email,
            "info@shop-epower.test",
        )

    # Проверяем строковое представление:
    # в админке и логах должны отображаться название компании.
    def test_company_settings_str(self):
        company_settings = CompanySettings.objects.create(
            company_name="Shop ePower LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
        )

        self.assertEqual(
            str(company_settings),
            "Shop ePower LLC",
        )