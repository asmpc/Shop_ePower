from shop_epower.core.models import BaseModel


from django.db import models



class ProductVariantGroup(BaseModel):
    """
    Groups several purchasable Products as variants of each other.

    IMPORTANT:
    Product is always a purchasable unit.
    Variants are only relationships between similar products
    such as color, size, version, etc.
    """

    name = models.CharField(
        max_length=255,
        verbose_name="Name",
    )

    variant_type = models.CharField(
        max_length=50,
        default="color",
        verbose_name="Variant type",
        help_text="For example: color, size, version, material.",
    )

    products = models.ManyToManyField(
        "catalog.Product",
        related_name="variant_groups",
        verbose_name="Products",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is active",
    )

    class Meta:
        verbose_name = "Product variant group"
        verbose_name_plural = "Product variant groups"

    def __str__(self):
        return f"{self.name} ({self.variant_type})"