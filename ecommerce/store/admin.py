from django.contrib import admin
from django.utils.html import format_html
import json

from .models import * # Asegúrate de que todos tus modelos están importados

# Clase Admin para Category
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)} # Rellena automáticamente el slug a partir del nombre
    search_fields = ('name',)

# Clase Admin para SubCategory
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'slug')
    prepopulated_fields = {'slug': ('name',)} # Rellena automáticamente el slug a partir del nombre
    list_filter = ('category',) # Permite filtrar por la categoría principal
    search_fields = ('name', 'category__name') # Buscar por nombre de subcategoría y nombre de categoría

# Modificación de ProductAdmin para incluir la subcategoría
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'digital', 'subcategory', 'has_digital_file') # Añadido 'subcategory'
    list_filter = ('digital', 'subcategory__category', 'subcategory') # Filtros por tipo y categoría/subcategoría
    search_fields = ('name', 'subcategory__name', 'subcategory__category__name') # Búsqueda mejorada
    # Añade 'subcategory' a los campos editables si no lo tienes ya en un fieldset
    fields = ('name', 'price', 'digital', 'image', 'digital_file', 'subcategory')


# Definir el inline para OrderItem (ya lo tenías)
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Campos de solo lectura y a mostrar para OrderItem en el admin de Order
    readonly_fields = ['product', 'quantity', 'date_added', 'get_total', 'download_token']
    fields = ['product', 'quantity', 'get_total', 'download_token']

# Definir el inline para ShippingAddress para usarlo en OrderAdmin
class ShippingAddressInline(admin.TabularInline):
    model = ShippingAddress
    extra = 0
    max_num = 1
    can_delete = False
    fields = ['address', 'city', 'state', 'zipcode', 'phone_number']
    readonly_fields = ['address', 'city', 'state', 'zipcode', 'phone_number']

# Clase Admin para el modelo Order
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'date_ordered',
        'complete',
        'get_cart_total',
        'get_cart_items',
        'shipping',
        'is_processed',
    )
    list_editable = ('is_processed',)
    list_filter = (
        'complete',
        'is_processed',
        'date_ordered',
        'customer'
    )
    search_fields = (
        'id__exact',
        'customer__name',
        'customer__email',
        'transaction_id'
    )
    inlines = [OrderItemInline, ShippingAddressInline]

    readonly_fields = (
        'date_ordered',
        'transaction_id',
        'customer',
        'get_cart_total',
        'get_cart_items',
        'complete',
    )
    fieldsets = (
        (None, {
            'fields': ('customer', 'complete', 'is_processed', 'transaction_id'),
        }),
        ('Información de la Orden', {
            'fields': ('date_ordered', 'get_cart_items', 'get_cart_total'),
            'classes': ('collapse',),
        }),
    )

    def cart_total(self, obj):
        return format_html("<div id='cart-total-display'>{}</div>", obj.get_cart_total)
    cart_total.short_description = "Total carrito"

    def get_cart_items(self, obj):
        return format_html("<div id='get_cart-items-display'>{}</div>", obj.get_cart_items)
    get_cart_items.short_description = "Total productos en carrito"

    class Media:
        js = ('/static/store/js/order_admin.js',)

# Clase Admin para OrderItem (ya la tenías)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product','order', 'quantity', 'date_added', 'get_total', 'requires_shipping')

# Clase Admin para Customer (ya la tenías)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email')
    search_fields = ('name', 'email')
    inlines = [ShippingAddressInline]

# Clase Admin para ShippingAddress (ya la tenías)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'address', 'city', 'state', 'zipcode', 'order')
    search_fields = ('customer__name', 'customer__email', 'address', 'city', 'zipcode')
    list_filter = ('state', 'city')

# --- REGISTROS DE MODELOS CON SUS CLASES ADMIN PERSONALIZADAS ---
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Product, ProductAdmin) # ¡REGISTRAR Product con ProductAdmin modificado!
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(ShippingAddress, ShippingAddressAdmin)

# --- NUEVOS REGISTROS PARA CATEGORÍAS ---
admin.site.register(Category, CategoryAdmin)
admin.site.register(SubCategory, SubCategoryAdmin)