from django.db import models


class PaymentMethod(models.TextChoices):
    ON_RECEIPT = "on_receipt", "On receipt"
    INVOICE = "invoice", "By invoice"
    ONLINE = "online", "Online payment"