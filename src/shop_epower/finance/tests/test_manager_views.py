from decimal import Decimal

from django.core.paginator import Page
from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import (
    AccountTransactionActorType,
    CustomerAccountStatus,
    CustomerAccountType,
)
from shop_epower.finance.services import (
    change_customer_account_status,
    create_legal_customer_account,
    create_personal_customer_account,
    record_customer_deposit,
)


class TestsManagerFinanceViews(TestCase):
    # При открытии раздела без поиска существующие счета не показываются.
    def test_account_list_starts_without_results(self):
        customer = create_test_user()
        create_personal_customer_account(user=customer)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["accounts"]), [])
        self.assertNotContains(response, customer.email)

    # Клиент не может открыть служебный список чужих финансовых счетов.
    def test_client_cannot_open_account_list(self):
        owner = create_test_user()
        create_personal_customer_account(user=owner)
        client_user = create_test_user()

        self.client.force_login(client_user)
        response = self.client.get(reverse("finance:manager_account_list"))

        self.assertEqual(response.status_code, 403)

    # Менеджер видит в навбаре ссылку на финансовые счета.
    def test_manager_sees_finance_link_in_navbar(self):
        manager = create_test_manager()
        self.client.force_login(manager)

        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            f'href="{reverse("finance:manager_account_list")}"',
        )

    # Админ видит ссылку на финансовый раздел.
    def test_admin_sees_finance_link_in_navbar(self):
        admin = create_test_admin()
        self.client.force_login(admin)

        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            f'href="{reverse("finance:manager_account_list")}"',
        )

    # Клиент не видит служебную ссылку.
    def test_client_does_not_see_finance_link_in_navbar(self):
        client_user = create_test_user()
        self.client.force_login(client_user)

        response = self.client.get(reverse("home"))

        self.assertNotContains(
            response,
            f'href="{reverse("finance:manager_account_list")}"',
        )

    # Поиск по части email находит счёт нужного клиента.
    def test_manager_finds_account_by_customer_email(self):
        first_user = create_test_user(email="finance-alice@example.com")
        second_user = create_test_user(email="finance-bob@example.com")
        first_account = create_personal_customer_account(user=first_user)
        create_personal_customer_account(user=second_user)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"q": "alice"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["accounts"]),
            [first_account],
        )
        self.assertContains(response, first_user.email)
        self.assertNotContains(response, second_user.email)

    # Поиск отправляется через GET и сохраняет введённое значение.
    def test_account_search_form_keeps_query(self):
        manager = create_test_manager()
        self.client.force_login(manager)

        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"q": "alice"},
        )

        self.assertContains(response, '<form method="get"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'value="alice"')

    # Широкий поиск показывает результаты постранично.
    def test_account_search_results_are_paginated(self):
        for index in range(21):
            customer = create_test_user(
                email=f"finance-search-{index}@example.com",
            )
            create_personal_customer_account(user=customer)

        manager = create_test_manager()
        self.client.force_login(manager)
        url = reverse("finance:manager_account_list")

        first_page = self.client.get(
            url,
            {
                "q": "finance-search",
                "account_type": CustomerAccountType.PERSONAL,
                "status": CustomerAccountStatus.ACTIVE,
            },
        )
        second_page = self.client.get(
            url,
            {
                "q": "finance-search",
                "account_type": CustomerAccountType.PERSONAL,
                "status": CustomerAccountStatus.ACTIVE,
                "page": 2,
            },
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(first_page.context["accounts"]), 20)
        self.assertEqual(len(second_page.context["accounts"]), 1)
        self.assertEqual(first_page.context["paginator"].count, 21)
        self.assertContains(
            first_page,
            '?q=finance-search&amp;account_type=personal&amp;status=active&amp;page=2">',
        )
        self.assertContains(
            second_page,
            '?q=finance-search&amp;account_type=personal&amp;status=active&amp;page=1">',
        )

    # Менеджер находит счёт клиента по части номера телефона.
    def test_manager_finds_account_by_customer_phone(self):
        first_user = create_test_user(phone="+375291111111")
        second_user = create_test_user(phone="+375292222222")
        first_account = create_personal_customer_account(user=first_user)
        create_personal_customer_account(user=second_user)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"q": "111111"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["accounts"]),
            [first_account],
        )
        self.assertContains(response, first_user.email)
        self.assertNotContains(response, second_user.email)

    # По УНП/ИНН находится юридический счёт, но не личный.
    def test_manager_finds_legal_account_by_tax_id(self):
        customer = create_test_user()
        create_personal_customer_account(user=customer)
        legal_profile = create_test_legal_profile(
            user=customer,
            tax_id="123456789",
        )
        legal_account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        other_customer = create_test_user()
        other_profile = create_test_legal_profile(
            user=other_customer,
            tax_id="987654321",
        )
        create_legal_customer_account(legal_profile=other_profile)

        manager = create_test_manager()
        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"q": "123456789"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["accounts"]),
            [legal_account],
        )

    # Один УНП может относиться к отдельным счетам разных клиентов.
    def test_tax_id_search_returns_accounts_of_both_customers(self):
        first_user = create_test_user()
        second_user = create_test_user()

        first_profile = create_test_legal_profile(
            user=first_user,
            tax_id="123456789",
        )
        second_profile = create_test_legal_profile(
            user=second_user,
            tax_id="123456789",
        )
        first_account = create_legal_customer_account(
            legal_profile=first_profile,
        )
        second_account = create_legal_customer_account(
            legal_profile=second_profile,
        )

        manager = create_test_manager()
        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"q": "123456789"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context["accounts"],
            [first_account, second_account],
        )

    # По точному номеру находится только нужный счёт.
    def test_manager_finds_account_by_id(self):
        first_user = create_test_user()
        second_user = create_test_user()
        first_account = create_personal_customer_account(user=first_user)
        create_personal_customer_account(user=second_user)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"account_id": str(first_account.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["accounts"]),
            [first_account],
        )

    # Некорректный номер счёта не вызывает ошибку сервера.
    def test_manager_search_with_invalid_account_id_returns_no_accounts(self):
        user = create_test_user()
        create_personal_customer_account(user=user)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"account_id": "abc"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["accounts"]), [])

    # Форма позволяет искать по номеру счёта и сохраняет введённый номер.
    def test_account_search_form_keeps_account_id(self):
        manager = create_test_manager()
        self.client.force_login(manager)

        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"account_id": "42"},
        )

        self.assertContains(response, 'name="account_id"')
        self.assertContains(response, 'value="42"')

    # Фильтр по типу показывает только личный счёт.
    def test_manager_filters_accounts_by_type(self):
        customer = create_test_user()
        personal_account = create_personal_customer_account(user=customer)
        legal_profile = create_test_legal_profile(user=customer)
        create_legal_customer_account(legal_profile=legal_profile)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"account_type": CustomerAccountType.PERSONAL},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["accounts"]),
            [personal_account],
        )

    # Фильтр ACTIVE не показывает неактивные счета.
    def test_manager_filters_accounts_by_status(self):
        active_user = create_test_user()
        inactive_user = create_test_user()
        active_account = create_personal_customer_account(user=active_user)
        inactive_account = create_personal_customer_account(user=inactive_user)
        manager = create_test_manager()

        change_customer_account_status(
            account=inactive_account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Account temporarily deactivated.",
            changed_by=manager,
        )

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"status": CustomerAccountStatus.ACTIVE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["accounts"]),
            [active_account],
        )

    # Форма показывает выбор типа и сохраняет его после поиска.
    def test_account_search_form_keeps_account_type(self):
        manager = create_test_manager()
        self.client.force_login(manager)

        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"account_type": CustomerAccountType.LEGAL},
        )

        self.assertContains(response, 'name="account_type"')
        self.assertContains(response, 'value="legal" selected')

    # Форма показывает выбор статуса и сохраняет его после поиска.
    def test_account_search_form_keeps_status(self):
        manager = create_test_manager()
        self.client.force_login(manager)

        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"status": CustomerAccountStatus.INACTIVE},
        )

        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'value="inactive" selected')

    # Подсказка различает пустую страницу и поиск без совпадений.
    def test_account_list_empty_message_reflects_search_state(self):
        manager = create_test_manager()
        self.client.force_login(manager)
        url = reverse("finance:manager_account_list")

        initial_response = self.client.get(url)
        filtered_response = self.client.get(
            url,
            {"account_type": CustomerAccountType.LEGAL},
        )

        self.assertContains(
            initial_response,
            "Enter a search term or choose a filter to find an account.",
        )
        self.assertContains(filtered_response, "No accounts found.")

    # Менеджер открывает страницу найденного финансового счёта.
    def test_manager_can_view_customer_account_detail(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_detail", args=[account.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account"], account)
        self.assertContains(response, customer.email)

    # Обычный клиент не может открыть служебную страницу чужого счёта.
    def test_client_cannot_open_account_detail(self):
        owner = create_test_user()
        account = create_personal_customer_account(user=owner)
        client_user = create_test_user()

        self.client.force_login(client_user)
        response = self.client.get(
            reverse("finance:manager_account_detail", args=[account.pk]),
        )

        self.assertEqual(response.status_code, 403)

    # Администратор может просматривать финансовый счёт клиента.
    def test_admin_can_view_customer_account_detail(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        admin = create_test_admin()

        self.client.force_login(admin)
        response = self.client.get(
            reverse("finance:manager_account_detail", args=[account.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["account"], account)

    # Результат поиска содержит ссылку на страницу найденного счёта.
    def test_account_search_result_links_to_detail(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_list"),
            {"account_id": str(account.pk)},
        )

        detail_url = reverse(
            "finance:manager_account_detail",
            args=[account.pk],
        )
        self.assertContains(response, f'href="{detail_url}"')

    # Страница показывает постраничную историю только выбранного счёта.
    def test_account_detail_shows_only_its_transactions(self):
        customer = create_test_user()
        other_customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        other_account = create_personal_customer_account(user=other_customer)

        own_transaction = record_customer_deposit(
            account=account,
            amount=Decimal("100.00"),
            operation_key="account-detail:own:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        other_transaction = record_customer_deposit(
            account=other_account,
            amount=Decimal("200.00"),
            operation_key="account-detail:other:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        manager = create_test_manager()
        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_detail", args=[account.pk]),
        )

        self.assertEqual(response.status_code, 200)
        transactions = response.context["transactions"]
        self.assertIsInstance(transactions, Page)
        self.assertEqual(list(transactions), [own_transaction])
        self.assertContains(response, own_transaction.operation_key)
        self.assertNotContains(response, other_transaction.operation_key)

    # История счёта показывает 20 операций на странице и ссылки перехода.
    def test_account_detail_transactions_are_paginated(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)

        for index in range(21):
            record_customer_deposit(
                account=account,
                amount=Decimal("1.00"),
                operation_key=f"account-detail:page:{index}",
                actor_type=AccountTransactionActorType.SYSTEM,
            )

        manager = create_test_manager()
        self.client.force_login(manager)
        url = reverse("finance:manager_account_detail", args=[account.pk])

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"transactions_page": 2})

        self.assertEqual(len(first_page.context["transactions"]), 20)
        self.assertEqual(len(second_page.context["transactions"]), 1)
        self.assertContains(first_page, 'href="?transactions_page=2">')
        self.assertContains(second_page, 'href="?transactions_page=1">')

    # В истории видны изменения и остатки после операции.
    def test_account_detail_shows_transaction_amounts(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)

        transaction = record_customer_deposit(
            account=account,
            amount=Decimal("123.45"),
            operation_key="account-detail:amounts:001",
            actor_type=AccountTransactionActorType.SYSTEM,
            comment="Bank transfer received.",
        )

        manager = create_test_manager()
        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_detail", args=[account.pk]),
        )

        currency = transaction.currency_snapshot
        self.assertContains(
            response,
            f"Available change: 123.45 {currency}",
        )
        self.assertContains(
            response,
            f"Available after: 123.45 {currency}",
        )
        self.assertContains(response, "Bank transfer received.")

    # На странице счёта видна причина и автор смены статуса.
    def test_account_detail_shows_status_history(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        manager = create_test_manager()

        change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Waiting for verification.",
            changed_by=manager,
        )
        history_entry = account.status_history.get()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_account_detail", args=[account.pk]),
        )

        self.assertEqual(response.status_code, 200)
        status_history = response.context["status_history"]
        self.assertIsInstance(status_history, Page)
        self.assertEqual(list(status_history), [history_entry])
        self.assertContains(response, "Waiting for verification.")
        self.assertContains(response, manager.email)

    # История статуса показывает 20 записей на странице.
    def test_account_detail_status_history_is_paginated(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        manager = create_test_manager()

        for index in range(21):
            new_status = (
                CustomerAccountStatus.INACTIVE
                if index % 2 == 0
                else CustomerAccountStatus.ACTIVE
            )
            change_customer_account_status(
                account=account,
                new_status=new_status,
                reason=f"Status change {index}.",
                changed_by=manager,
            )

        self.client.force_login(manager)
        url = reverse("finance:manager_account_detail", args=[account.pk])

        first_page = self.client.get(url)
        second_page = self.client.get(url, {"status_page": 2})

        self.assertEqual(len(first_page.context["status_history"]), 20)
        self.assertEqual(len(second_page.context["status_history"]), 1)
        self.assertContains(first_page, 'href="?status_page=2">')
        self.assertContains(second_page, 'href="?status_page=1">')

    # Общий журнал при первом открытии не показывает операции клиентов.
    def test_transaction_journal_starts_without_results(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        transaction = record_customer_deposit(
            account=account,
            amount=Decimal("100.00"),
            operation_key="journal:initial:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )
        manager = create_test_manager()

        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_transaction_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["transactions"]), [])
        self.assertContains(response, 'name="operation_key"')
        self.assertNotContains(response, transaction.operation_key)

    # Поиск по части ключа показывает нужную операцию,
    # но не подмешивает операции других клиентов.
    def test_transaction_journal_searches_by_operation_key(self):
        first_customer = create_test_user()
        first_account = create_personal_customer_account(user=first_customer)
        matching_transaction = record_customer_deposit(
            account=first_account,
            amount=Decimal("100.00"),
            operation_key="journal:find:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        second_customer = create_test_user()
        second_account = create_personal_customer_account(user=second_customer)
        other_transaction = record_customer_deposit(
            account=second_account,
            amount=Decimal("50.00"),
            operation_key="other:deposit:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        manager = create_test_manager()
        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_transaction_list"),
            {"operation_key": "journal:find"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["transactions"]),
            [matching_transaction],
        )
        self.assertContains(response, matching_transaction.operation_key)
        self.assertNotContains(response, other_transaction.operation_key)

    # Клиенту запрещён доступ к общему журналу,
    # даже если он знает ключ конкретной операции.
    def test_transaction_journal_forbids_customer(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        record_customer_deposit(
            account=account,
            amount=Decimal("100.00"),
            operation_key="journal:private:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        self.client.force_login(customer)
        response = self.client.get(
            reverse("finance:manager_transaction_list"),
            {"operation_key": "journal:private:001"},
        )

        self.assertEqual(response.status_code, 403)

    # Администратор может найти операцию в общем журнале.
    def test_transaction_journal_allows_admin(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        transaction = record_customer_deposit(
            account=account,
            amount=Decimal("100.00"),
            operation_key="journal:admin:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        admin = create_test_admin()
        self.client.force_login(admin)
        response = self.client.get(
            reverse("finance:manager_transaction_list"),
            {"operation_key": "journal:admin:001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["transactions"]),
            [transaction],
        )

    # Журнал показывает не больше 20 операций на странице,
    # а переход сохраняет введённый поисковый запрос.
    def test_transaction_journal_is_paginated_and_preserves_search(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)

        for index in range(21):
            record_customer_deposit(
                account=account,
                amount=Decimal("1.00"),
                operation_key=f"journal-page-{index:03d}",
                actor_type=AccountTransactionActorType.SYSTEM,
            )

        manager = create_test_manager()
        self.client.force_login(manager)
        url = reverse("finance:manager_transaction_list")

        first_page = self.client.get(
            url,
            {"operation_key": "journal-page-"},
        )
        second_page = self.client.get(
            url,
            {"operation_key": "journal-page-", "page": 2},
        )

        self.assertEqual(len(first_page.context["transactions"]), 20)
        self.assertEqual(len(second_page.context["transactions"]), 1)
        self.assertContains(
            first_page,
            'href="?operation_key=journal-page-&amp;page=2"',
        )
        self.assertContains(
            second_page,
            'href="?operation_key=journal-page-&amp;page=1"',
        )

    # Менеджер может перейти из раздела финансов в общий журнал операций.
    def test_account_list_links_to_transaction_journal(self):
        manager = create_test_manager()
        self.client.force_login(manager)

        response = self.client.get(
            reverse("finance:manager_account_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("finance:manager_transaction_list")}"',
        )

    # Посетителя без входа журнал отправляет на страницу авторизации.
    def test_transaction_journal_redirects_anonymous_user_to_login(self):
        url = reverse("finance:manager_transaction_list")

        response = self.client.get(
            url,
            {"operation_key": "journal:any"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response["Location"],
        )

    # Общий журнал показывает денежные изменения операции.
    def test_transaction_journal_shows_balance_changes(self):
        customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        transaction = record_customer_deposit(
            account=account,
            amount=Decimal("123.45"),
            operation_key="journal:amounts:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        manager = create_test_manager()
        self.client.force_login(manager)
        response = self.client.get(
            reverse("finance:manager_transaction_list"),
            {"operation_key": transaction.operation_key},
        )

        currency = transaction.currency_snapshot
        self.assertContains(
            response,
            f"Available change: 123.45 {currency}",
        )
        self.assertContains(
            response,
            f"Debt change: 0.00 {currency}",
        )
        self.assertContains(
            response,
            f"Available after: 123.45 {currency}",
        )
        self.assertContains(
            response,
            f"Debt after: 0.00 {currency}",
        )
