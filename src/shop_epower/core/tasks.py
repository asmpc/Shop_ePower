from celery import shared_task


@shared_task
def check_celery_connection():
    """
    Проверяет базовую работу Celery worker.
    """

    return "Celery is working"