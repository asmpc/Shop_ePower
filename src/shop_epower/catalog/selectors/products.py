from django.db.models import Q

from shop_epower.catalog.models import Product, Category



def get_category_with_descendants(category):
    categories = [category]

    children = Category.objects.filter(parent=category)

    for child in children:
        categories.extend(
            get_category_with_descendants(child)
        )

    return categories

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


    category_slug = params.get("category")

    if category_slug:
        try:
            category = Category.objects.get(slug=category_slug)
        except Category.DoesNotExist:
            return queryset.none()

        categories = get_category_with_descendants(category)

        queryset = queryset.filter(
            category__in=categories
        )


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

