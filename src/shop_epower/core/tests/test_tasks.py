from unittest.mock import patch

from django.test import TestCase

from shop_epower.core.tasks import (
    cleanup_expired_jwt_tokens,
)


class TestsCoreTasks(TestCase):

    # Проверяем, что задача запускает
    # очистку просроченных JWT токенов.
    @patch(
        "shop_epower.core.tasks.call_command",
    )
    def test_cleanup_expired_jwt_tokens(
        self,
        mocked_call_command,
    ):

        cleanup_expired_jwt_tokens()

        mocked_call_command.assert_called_once_with(
            "flushexpiredtokens",
        )