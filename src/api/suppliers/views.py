from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from shop_epower.suppliers.models import Supplier, SupplierProduct

from api.suppliers.serializers import (
    SupplierSerializer,
    SupplierProductSerializer,
)


class SupplierViewSet(ReadOnlyModelViewSet):

    serializer_class = SupplierSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    queryset = (
        Supplier.objects
        .filter(is_active=True)
        .order_by("id")
    )


class SupplierProductViewSet(ReadOnlyModelViewSet):

    serializer_class = SupplierProductSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    queryset = (
        SupplierProduct.objects
        .select_related(
            "supplier",
            "product",
        )
        .filter(
            is_active=True,
            supplier__is_active=True,
        )
        .order_by("id")
    )