from celery import shared_task
from django.core.management import call_command


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={
        "max_retries": 3,
    },
)
def cleanup_expired_jwt_tokens():
    """
    Удаляет просроченные JWT токены.
    """

    call_command(
        "flushexpiredtokens",
    )


@shared_task
def check_celery_connection():
    """
    Проверяет базовую работу Celery worker.
    """

    return "Celery is working"