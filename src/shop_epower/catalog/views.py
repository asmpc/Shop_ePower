from django.views.generic import DetailView

from django.views.generic import ListView
from shop_epower.catalog.selectors.products import (
    get_product_list_queryset,
    get_product_detail_queryset,
)

from shop_epower.catalog.models import Product, Brand, Category

from shop_epower.suppliers.models import CurrencyRate
from shop_epower.accounts.services.roles import is_manager

from shop_epower.suppliers.services.stock import (
    get_product_inventory_detailed,
    get_supplier_inventory_details,
    get_product_inventory_public,
)
from shop_epower.suppliers.services.cost import get_product_cost_summary
from shop_epower.catalog.selectors.product_data import prepare_product_for_user



class ProductListView(ListView):

    model = Product
    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_manager"] = is_manager(self.request.user)

        user = self.request.user

        for product in context["products"]:
            prepare_product_for_user(product, user)

        context['brands'] = Brand.objects.filter(is_active=True)
        context['categories'] = Category.objects.filter(is_active=True)

        currency_rates = {
            "BYN": 1,
        }

        for rate in CurrencyRate.objects.all():
            currency_rates[rate.currency] = float(rate.rate_to_BYN)

        context["currency_rates"] = currency_rates

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

        currency_rates = {
            "BYN": 1,
        }

        for rate in CurrencyRate.objects.all():
            currency_rates[rate.currency] = float(rate.rate_to_BYN)

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