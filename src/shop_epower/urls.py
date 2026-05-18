from django.urls import path, re_path, include



urlpatterns = [

    path('accounts/', include('shop_epower.accounts.urls')),

    path(
        '',
        include('shop_epower.core.urls'),
    ),

    path(
        'accounts/',
        include('shop_epower.accounts.urls'),
    ),

]