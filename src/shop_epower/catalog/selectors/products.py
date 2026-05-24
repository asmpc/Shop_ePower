# shop_epower/catalog/selectors/products.py

from django.db.models import Q

from shop_epower.catalog.models import Product


def get_product_list_queryset(params=None):
    params = params or {}

    queryset = Product.objects.filter(
        is_active=True
    ).select_related(
        "brand",
        "category",
    ).prefetch_related(
        "images",
    )

    search = params.get("search")
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(manufacturer_article__icontains=search)
            | Q(brand__name__icontains=search)
        )

    brand = params.get("brand")
    if brand:
        queryset = queryset.filter(brand__slug=brand)

    category = params.get("category")
    if category:
        queryset = queryset.filter(category__slug=category)

    sort = params.get("sort")
    if sort == "name":
        queryset = queryset.order_by("name")
    elif sort == "name_desc":
        queryset = queryset.order_by("-name")
    elif sort == "newest":
        queryset = queryset.order_by("-created_at")

    return queryset

def get_product_detail_queryset():
    return Product.objects.filter(
        is_active=True
    ).select_related(
        "brand",
        "category",
    ).prefetch_related(
        "variants",
        "images",
        "variants__images",
    )