from django.views.generic import DetailView

from django.views.generic import ListView
from django.db.models import Q

from shop_epower.catalog.models import Product, Brand, Category



class ProductListView(ListView):

    model = Product
    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = 12


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        for product in context['products']:
            product.final_price = product.get_price_for_user(user)

        context['brands'] = Brand.objects.filter(is_active=True)
        context['categories'] = Category.objects.filter(is_active=True)

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

        # 🔥 NEW PART: attach computed price
        user = self.request.user

        for product in queryset:
            product.final_price = product.get_price_for_user(user)

        return queryset


class ProductDetailView(DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        product = context['product']
        user = self.request.user

        product.final_price = product.get_price_for_user(user)

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