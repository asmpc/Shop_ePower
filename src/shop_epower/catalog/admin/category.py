from django.contrib import admin
from shop_epower.catalog.models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'parent',
        'is_active',
        'sort_order',
        'created_at',
    )

    list_filter = (
        'is_active',
        'parent',
    )

    search_fields = (
        'name',
        'slug',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }

    ordering = (
        'sort_order',
        'name',
    )

    list_editable = (
        'is_active',
        'sort_order',
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
                'parent',
                'image',
                'is_active',
                'sort_order',
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