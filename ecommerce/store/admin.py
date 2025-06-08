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

admin.site.register(Customer)
admin.site.register(Product)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(ShippingAddress)

