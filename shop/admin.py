from django.contrib import admin

from .models import Product, Purchase


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price')
    search_fields = ('name', 'category')


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'product', 'discount_percent', 'total', 'date')
    search_fields = ('person', 'product__name')
    readonly_fields = ('customer', 'person', 'product', 'address', 'base_price',
                       'discount_percent', 'total', 'date')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
