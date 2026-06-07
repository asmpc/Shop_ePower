from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from shop_epower.core.models import BaseModel


class Cart(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True,
        verbose_name=_("User"),
    )

    session_key = models.CharField(
        max_length=40,
        blank=True,
        verbose_name=_("Session key"),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is active"),
    )

    class Meta:
        verbose_name = _("Cart")
        verbose_name_plural = _("Carts")

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        if self.user:
            return f"Cart for {self.user}"
        return f"Cart session {self.session_key}"