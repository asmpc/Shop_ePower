from django.test import TestCase

from shop_epower.payments.tests.helpers import (
    create_test_company_settings,
)
from shop_epower.payments.selectors.company_settings import (
    get_company_settings,
)



class TestsCompanySettingsSelectors(TestCase):

    # Проверяем получение текущих реквизитов компании.
    def test_get_company_settings(self):

        company_settings = create_test_company_settings(
            company_name="Shop ePower LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
        )

        result = get_company_settings()

        self.assertEqual(
            result,
            company_settings,
        )

    # Проверяем ситуацию,
    # когда реквизиты компании отсутствуют.
    def test_get_company_settings_returns_none(self):
        self.assertIsNone(
            get_company_settings()
        )