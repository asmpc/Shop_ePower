from rest_framework.response import Response

from rest_framework.generics import ListAPIView, RetrieveAPIView

from shop_epower.catalog.selectors.products import (
    get_product_list_queryset,
    get_product_detail_queryset,
)
from shop_epower.catalog.selectors.product_data import prepare_product_for_user

from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
)



class ProductListAPIView(ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return get_product_list_queryset(self.request.query_params)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        for product in queryset:
            prepare_product_for_user(product, request.user)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data)


class ProductDetailAPIView(RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return get_product_detail_queryset()

    def retrieve(self, request, *args, **kwargs):
        product = self.get_object()

        prepare_product_for_user(product, request.user)

        serializer = self.get_serializer(product)

        return Response(serializer.data)