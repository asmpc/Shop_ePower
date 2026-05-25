from django.urls import path, re_path, include



urlpatterns = [

    path(
        '',
        include('shop_epower.core.urls'),
    ),

    path('accounts/', include('shop_epower.accounts.urls')),

    path('catalog/', include('shop_epower.catalog.urls')),

    path("cart/", include("shop_epower.cart.urls")),


]
