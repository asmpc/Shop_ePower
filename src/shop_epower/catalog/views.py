from django.views.generic import DetailView

from django.views.generic import ListView
from django.db.models import Q

from shop_epower.catalog.models import Product, Brand, Category
from shop_epower.catalog.models import Brand, Category



class ProductListView(ListView):

    model = Product
    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['brands'] = Brand.objects.all()
        context['categories'] = Category.objects.all()

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

        # ----------------------------
        # SEARCH
        # ----------------------------
        search = self.request.GET.get('search')

        if search:

            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(manufacturer_article__icontains=search) |
                Q(brand__name__icontains=search)
            )

        # ----------------------------
        # FILTER: brand
        # ----------------------------
        brand = self.request.GET.get('brand')

        if brand:

            queryset = queryset.filter(brand__slug=brand)

        # ----------------------------
        # FILTER: category
        # ----------------------------
        category = self.request.GET.get('category')

        if category:

            queryset = queryset.filter(category__slug=category)

        # ----------------------------
        # SORTING
        # ----------------------------
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