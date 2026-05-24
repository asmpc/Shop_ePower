from django.urls import path, re_path, include



urlpatterns = [

    path(
        '',
        include('shop_epower.core.urls'),
    ),

# existing app urls
    path('accounts/', include('shop_epower.accounts.urls')),

    path('catalog/', include('shop_epower.catalog.urls')),

    # new structured API
    path("api/accounts/", include("shop_epower.api.accounts.urls")),

]
