from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from .models import (
    User,
    PriceCategory,
    LegalProfile,
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


class LegalProfileInline(admin.StackedInline):
    model = LegalProfile
    can_delete = False
    extra = 0

    fieldsets = (
        (
            'Юридическое лицо',
            {
                'fields': (
                    'is_legal_entity',
                    'company_name',
                    'tax_id',
                    'legal_address',
                    'bank_name',
                    'bank_account',
                )
            }
        ),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    inlines = [LegalProfileInline]

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


@admin.register(LegalProfile)
class LegalProfileAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'is_legal_entity',
        'company_name',
        'tax_id',
        'bank_name',
        'created_at',
    )

    list_filter = (
        'is_legal_entity',
        'created_at',
    )

    search_fields = (
        'company_name',
        'tax_id',
        'user__email',
        'user__username',
    )