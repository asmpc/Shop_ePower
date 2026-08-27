from django.urls import include, path

urlpatterns = [

    path(
        '',
        include('shop_epower.core.urls'),
    ),

    path('accounts/', include('shop_epower.accounts.urls')),

    path('catalog/', include('shop_epower.catalog.urls')),

    path("cart/", include("shop_epower.cart.urls")),

    path("orders/", include("shop_epower.orders.urls")),

    path("chat/", include("shop_epower.chat.urls")),


]
