from django.contrib import admin
from django.utils.html import format_html
import json

from .models import *

# Register your models here.

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'date_ordered', 'complete', 'get_cart_total', 'get_cart_items', 'shipping')
    inlines = [OrderItemInline]
    readonly_fields = ('cart_total', 'get_cart_items')

    def cart_total(self, obj):
        prices = {str(p.id): float(p.price) for p in Product.objects.all()}
        prices_json = json.dumps(prices)

        return format_html("""
            <div id="cart-total-display">{}</div>
            <script type="application/json" id="product-price-data">{}</script>
        """, obj.get_cart_total, prices_json)

    cart_total.short_description = "Total cart"

    def get_cart_items(self, obj):
        return format_html("<div id='get_cart-items-display'>{}</div>", obj.get_cart_items)

    get_cart_items.short_description = "Total products in cart"

    class Media:
        js = ('/static/store/js/order_admin.js',)

class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product','order', 'quantity', 'date_added', 'get_total', 'requires_shipping')

class ShippingAddressInline(admin.TabularInline):
    # Relaciona este inline con el modelo ShippingAddress
    model = ShippingAddress
    # Determina cuántos formularios vacíos se muestran para añadir nuevas direcciones.
    # 0 significa que no se muestran vacíos a menos que se pulse "Añadir otro".
    extra = 0
    # Puedes especificar los campos que quieres mostrar y/o los que serán de solo lectura
    # fields = ['address', 'city', 'state', 'zipcode']
    # readonly_fields = ['order'] # Si no quieres que el pedido se modifique desde aquí

class CustomerAdmin(admin.ModelAdmin):
    # Campos que se mostrarán en la lista de clientes en el panel de administración
    list_display = ('name', 'email')
    # Campos por los que se puede buscar
    search_fields = ('name', 'email')
    # ¡Añadimos el inline aquí!
    inlines = [ShippingAddressInline]

class ShippingAddressAdmin(admin.ModelAdmin):
    # Campos que se mostrarán en la lista de direcciones de envío
    list_display = ('customer', 'address', 'city', 'state', 'zipcode', 'order')
    # Campos por los que se puede buscar en la lista de direcciones
    search_fields = ('customer__name', 'customer__email', 'address', 'city', 'zipcode')
    # Opcional: Filtros para la lista de direcciones
    list_filter = ('state', 'city')

admin.site.register(Customer, CustomerAdmin)
admin.site.register(Product)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(ShippingAddress, ShippingAddressAdmin)

