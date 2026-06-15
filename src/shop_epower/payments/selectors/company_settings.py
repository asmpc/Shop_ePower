from shop_epower.payments.models import (
    CompanySettings,
)


def get_company_settings():
    """
    Возвращает текущие реквизиты компании.

    Используется для:
    - Invoice generation
    - PDF documents
    - Commercial offers
    - Future integrations
    """

    return (
        CompanySettings.objects
        .first()
    )