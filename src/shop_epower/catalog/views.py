from django.views.generic import DetailView

from django.views.generic import ListView
from django.db.models import Q

from shop_epower.catalog.models import Product, Brand, Category

from shop_epower.suppliers.models import CurrencyRate
from shop_epower.accounts.services.roles import is_manager

from shop_epower.suppliers.services.stock import (
    get_product_inventory_detailed,
    get_supplier_inventory_details,
    get_product_inventory_public,
)



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
            product.final_price = product.get_price_for_user(user)
            product.inventory = get_product_inventory_public(product)

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
        queryset = Product.objects.filter(
            is_active=True
        ).select_related(
            'brand',
            'category'
        ).prefetch_related(
            'images'
        )

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(manufacturer_article__icontains=search) |
                Q(brand__name__icontains=search)
            )

        brand = self.request.GET.get('brand')
        if brand:
            queryset = queryset.filter(brand__slug=brand)

        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        sort = self.request.GET.get('sort')
        if sort == 'name':
            queryset = queryset.order_by('name')
        elif sort == 'name_desc':
            queryset = queryset.order_by('-name')
        elif sort == 'newest':
            queryset = queryset.order_by('-created_at')

        return queryset


class ProductDetailView(DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["is_manager"] = is_manager(self.request.user)

        product = context['product']
        user = self.request.user

        product.final_price = product.get_price_for_user(user)
        product.inventory = get_product_inventory_public(product)

        currency_rates = {
            "BYN": 1,
        }

        for rate in CurrencyRate.objects.all():
            currency_rates[rate.currency] = float(rate.rate_to_BYN)

        context["currency_rates"] = currency_rates

        manager = is_manager(self.request.user)

        context["is_manager"] = manager

        if manager:
            context["supplier_inventory_details"] = get_supplier_inventory_details(product)

        return context

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True
        ).select_related(
            'brand',
            'category'
        ).prefetch_related(
            'variants',
            'images',
            'variants__images'
        )


def get_brand_list(self):
    return Brand.objects.filter(is_active=True)


def get_category_list(self):
    return Category.objects.filter(is_active=True)