from django.db import models

class GlobalMarkup(models.Model):
    """
    Централизованное место для хранения процентной наценки.
    В будущем можно расширить на группы товаров.
    """
    name = models.CharField(max_length=255, default="Default", unique=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.percent}%)"