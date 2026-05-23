from django.contrib import admin

from shop_epower.catalog.models import Brand


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'slug',
        'is_active',
        'created_at',
    )

    list_filter = (
        'is_active',
        'created_at',
    )

    search_fields = (
        'name',
        'slug',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }

    ordering = (
        'name',
    )

    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Main info', {
            'fields': (
                'name',
                'slug',
                'description',
                'logo',
                'is_active',
            )
        }),
        ('System info', {
            'fields': (
                'id',
                'created_at',
                'updated_at',
            )
        }),
    )