from django.contrib import admin
from django.utils.html import format_html
import json

from .models import * # Asegúrate de que todos tus modelos están importados

# Definir el inline para OrderItem (ya lo tenías)
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Campos de solo lectura y a mostrar para OrderItem en el admin de Order
    readonly_fields = ['product', 'quantity', 'date_added', 'get_total', 'download_token']
    fields = ['product', 'quantity', 'get_total', 'download_token'] # Asegúrate que 'get_total' es una propiedad en OrderItem si la usas

# Definir el inline para ShippingAddress para usarlo en OrderAdmin
class ShippingAddressInline(admin.TabularInline): # Puedes usar TabularInline o StackedInline
    model = ShippingAddress
    extra = 0
    max_num = 1 # Normalmente solo hay una dirección de envío por pedido
    can_delete = False # No permitir borrar la dirección asociada a un pedido
    # Queremos que la dirección sea de solo lectura en la vista de la orden
    fields = ['address', 'city', 'state', 'zipcode', 'phone_number']
    readonly_fields = ['address', 'city', 'state', 'zipcode', 'phone_number'] # Hacer todos los campos de solo lectura

# Clase Admin para el modelo Order
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'date_ordered',
        'complete', # Mostrará "PAGO COMPLETADO" por el verbose_name en models.py
        'get_cart_total',
        'get_cart_items',
        'shipping',
        'is_processed', # <-- NUEVO: Añade este campo a la lista
    )
    # Permite editar 'is_processed' directamente desde la lista de pedidos
    list_editable = ('is_processed',) # <-- NUEVO: Permite el checkbox en la lista
    # Filtros laterales para la lista de pedidos
    list_filter = (
        'complete',
        'is_processed', # <-- NUEVO: Permite filtrar por "PEDIDO GESTIONADO"
        'date_ordered',
        'customer'
    )
    # Campos por los que se puede buscar
    search_fields = (
        'id__exact',
        'customer__name',
        'customer__email',
        'transaction_id'
    )
    # Inlines para ver OrderItems y ShippingAddress desde la vista de detalle de Order
    inlines = [OrderItemInline, ShippingAddressInline] # <-- Añade ShippingAddressInline aquí

    # Campos de solo lectura en la vista de detalle del pedido
    readonly_fields = (
        'date_ordered',
        'transaction_id',
        'customer',
        'get_cart_total',
        'get_cart_items',
        'complete', # 'complete' se gestiona por el sistema de pago, no manualmente
        # 'cart_total', # Ya es un método que se puede usar en list_display, no tiene que ser readonly_fields
        # 'get_cart_items' # Lo mismo, ya es un método
    )
    # Organización de los campos en la vista de detalle de la orden
    fieldsets = (
        (None, {
            'fields': ('customer', 'complete', 'is_processed', 'transaction_id'),
        }),
        ('Información de la Orden', {
            'fields': ('date_ordered', 'get_cart_items', 'get_cart_total'), # Usa los métodos directamente aquí
            'classes': ('collapse',), # Opcional: hace que esta sección sea colapsable
        }),
    )

    # Tus métodos personalizados para mostrar totales
    def cart_total(self, obj):
        # Esta función ahora solo devuelve el valor, sin el script.
        # El script 'order_admin.js' debería manejar la parte de actualización dinámica si es necesario.
        return format_html("<div id='cart-total-display'>{}</div>", obj.get_cart_total)

    cart_total.short_description = "Total carrito" # Cambiado a "Total carrito" para ser más específico

    def get_cart_items(self, obj):
        return format_html("<div id='get_cart-items-display'>{}</div>", obj.get_cart_items)

    get_cart_items.short_description = "Total productos en carrito" # Cambiado a "Total productos en carrito"

    class Media:
        js = ('/static/store/js/order_admin.js',) # Si este JS es para el admin, déjalo

# Clase Admin para OrderItem (ya la tenías)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product','order', 'quantity', 'date_added', 'get_total', 'requires_shipping')

# Clase Admin para Customer (ya la tenías)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email')
    search_fields = ('name', 'email')
    inlines = [ShippingAddressInline] # Este inline aquí está bien para el Customer

# Clase Admin para ShippingAddress (ya la tenías)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'address', 'city', 'state', 'zipcode', 'order')
    search_fields = ('customer__name', 'customer__email', 'address', 'city', 'zipcode')
    list_filter = ('state', 'city')

# --- REGISTROS DE MODELOS CON SUS CLASES ADMIN PERSONALIZADAS ---
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Product)
admin.site.register(Order, OrderAdmin) # REGISTRAR Order con OrderAdmin
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(ShippingAddress, ShippingAddressAdmin)