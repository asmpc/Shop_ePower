from django.views.generic import DetailView, ListView

from shop_epower.accounts.services.roles import is_manager
from shop_epower.catalog.models import Brand, Category, Product
from shop_epower.catalog.selectors.product_data import prepare_product_for_user
from shop_epower.catalog.selectors.products import (
    get_product_detail_queryset,
    get_product_list_queryset,
)
from shop_epower.core.currency import get_base_currency
from shop_epower.suppliers.models import CurrencyRate
from shop_epower.suppliers.services.cost import get_product_cost_summary
from shop_epower.suppliers.services.stock import (
    get_supplier_inventory_details,
)


class CategoryListView(ListView):

    model = Category
    template_name = "catalog/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.filter(
            parent__isnull=True,
            is_active=True,
        ).prefetch_related(
            "children",
        )


class ProductListView(ListView):

    model = Product
    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get("per_page", self.paginate_by)

        allowed_values = [12, 24, 48]

        try:
            per_page = int(per_page)
        except ValueError:
            return self.paginate_by

        if per_page not in allowed_values:
            return self.paginate_by

        return per_page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_manager"] = is_manager(self.request.user)

        user = self.request.user

        for product in context["products"]:
            prepare_product_for_user(product, user)

        context['brands'] = Brand.objects.filter(is_active=True)
        context["categories"] = Category.objects.filter(
            parent__isnull=True,
            is_active=True,
        ).prefetch_related(
            "children",
        )

        currency_rates = {
            rate.currency: float(rate.rate_to_base_currency)
            for rate in CurrencyRate.objects.all()
        }

        currency_rates[get_base_currency()] = 1

        context["currency_rates"] = currency_rates
        context["per_page"] = self.get_paginate_by(self.get_queryset())

        params = self.request.GET.copy()
        params.pop("page", None)

        base_filter_params = params.copy()
        base_filter_params.pop("category", None)

        base_filter_query = base_filter_params.urlencode()

        context["base_filter_query"] = base_filter_query

        if base_filter_query:
            context["base_filter_query_prefix"] = f"{base_filter_query}&"
        else:
            context["base_filter_query_prefix"] = ""

        category_only_params = params.copy()
        category_only_params.pop("search", None)
        category_only_params.pop("brand", None)
        category_only_params.pop("sort", None)

        context["category_only_query"] = category_only_params.urlencode()

        pagination_params = self.request.GET.copy()
        pagination_params.pop("page", None)

        context["pagination_query"] = pagination_params.urlencode()

        return context

    def get_queryset(self):
        return get_product_list_queryset(self.request.GET)

class ProductDetailView(DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["is_manager"] = is_manager(self.request.user)

        product = context['product']
        user = self.request.user

        prepare_product_for_user(product, user)

        variant_groups = self.object.variant_groups.filter(is_active=True)

        variants = []

        for group in variant_groups:
            for product in group.products.exclude(id=self.object.id):
                variants.append(product)

        context["variants"] = variants


        from shop_epower.core.currency import get_base_currency

        currency_rates = {
            rate.currency: float(rate.rate_to_base_currency)
            for rate in CurrencyRate.objects.all()
        }

        currency_rates[get_base_currency()] = 1

        context["currency_rates"] = currency_rates

        manager = is_manager(self.request.user)

        if manager:
            context["supplier_inventory_details"] = get_supplier_inventory_details(product)
            context["cost_summary"] = get_product_cost_summary(product)

        context["is_manager"] = manager

        if manager:
            context["supplier_inventory_details"] = get_supplier_inventory_details(product)

        return context



    def get_queryset(self):
        return get_product_detail_queryset()


def get_brand_list(self):
    return Brand.objects.filter(is_active=True)


def get_category_list(self):
    return Category.objects.filter(is_active=True)