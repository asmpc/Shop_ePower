from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from .models import (
    User,
    PriceCategory,
)


@admin.register(PriceCategory)
class PriceCategoryAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'discount_percent',
    )

    search_fields = (
        'name',
    )

    ordering = (
        'id',
    )

@admin.register(User)
class CustomUserAdmin(UserAdmin):

    list_display = (
        'id',
        'email',
        'username',
        'role',
        'is_staff',
        'is_active',
        'price_category',
    )

    list_display_links = ('id', 'email', 'username',)

    list_filter = (
        'role',
        'is_staff',
        'is_active',
        'price_category',
    )

    search_fields = (
        'email',
        'username',
    )

    ordering = (
        'id',
    )

    fieldsets = (

        (
            'Authentication',
            {
                'fields': (
                    'email',
                    'username',
                    'password',
                )
            }
        ),

        (
            'Roles & Permissions',
            {
                'fields': (
                    'role',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                    'price_category',
                )
            }
        ),

        (
            'Important dates',
            {
                'fields': (
                    'last_login',
                    'date_joined',
                )
            }
        ),
    )