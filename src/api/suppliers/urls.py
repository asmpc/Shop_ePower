from django.urls import include, path

from rest_framework.routers import DefaultRouter

from api.suppliers.views import (
    SupplierViewSet,
    SupplierProductViewSet,
)


app_name = "suppliers_api"


router = DefaultRouter()

router.register(
    "suppliers",
    SupplierViewSet,
    basename="supplier",
)

router.register(
    "supplier-products",
    SupplierProductViewSet,
    basename="supplier-product",
)


urlpatterns = [
    path(
        "",
        include(router.urls),
    ),
]