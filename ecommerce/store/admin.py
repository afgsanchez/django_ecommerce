from django.contrib import admin
from django.utils.html import format_html
import json
from .models import * # Asegúrate de que todos tus modelos están importados
from django.utils import timezone # Importar para obtener la hora actual


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


# --- INLINE PARA LAS IMÁGENES ADICIONALES ---
# Esto permite añadir y gestionar las imágenes de un producto directamente
# desde la página de edición de ese producto en el admin.
class ProductImageInline(admin.TabularInline):  # Puedes usar admin.StackedInline para un diseño vertical
    model = ProductImage
    extra = 1  # Cuántos formularios vacíos adicionales se muestran para añadir nuevas imágenes
    fields = ['image', 'alt_text', 'order']  # Campos a mostrar para cada imagen
    # Opcional: Si quieres un campo de solo lectura para la URL de la imagen
    # readonly_fields = ['image_preview']
    # def image_preview(self, obj):
    #     if obj.image:
    #         from django.utils.html import format_html
    #         return format_html('<img src="{}" style="max-height: 80px;"/>', obj.image.url)
    #     return "No Image"
    # image_preview.short_description = "Previsualización"


# --- REGISTRO DEL MODELO PRODUCT ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Campos que se muestran en la tabla de lista de productos en el admin
    list_display = ('name', 'price', 'digital', 'subcategory', 'imageURL', 'has_digital_file')

    # Filtros laterales en la lista de productos
    list_filter = ('digital', 'subcategory__category', 'subcategory')

    # Campos por los que se puede buscar en la barra de búsqueda del admin
    search_fields = ('name', 'description', 'long_description', 'subcategory__name', 'subcategory__category__name')

    # Definición de las secciones y campos en el formulario de edición de un producto
    fieldsets = (
        (None, {  # Sección principal, sin título
            'fields': ('name', 'price', 'subcategory', 'digital', 'image')
        }),
        ('Descripción y Detalles', {  # Nueva sección para las descripciones
            'fields': ('description', 'long_description'),
            'description': 'Información detallada para la página del producto y listados.'
        }),
        ('Archivos Digitales', {  # Sección para productos digitales
            'fields': ('digital_file',),
            'classes': ('collapse',),  # Esto hace que la sección sea colapsable por defecto
            'description': 'Configura el archivo descargable si el producto es digital.'
        }),
        # Puedes añadir más secciones aquí si incluyes campos como 'stock', 'sku', etc.
    )

    # Conecta el inline de ProductImage al ProductAdmin
    inlines = [ProductImageInline]

    # Orden por defecto en la lista de productos (opcional, si no está en Meta del modelo)
    # ordering = ['name']


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




@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'email', 'asunto', 'fecha_envio', 'leido', 'fecha_lectura') # Añadir fecha_lectura
    list_filter = ('leido', 'fecha_envio', 'fecha_lectura') # Filtrar también por fecha_lectura
    search_fields = ('nombre', 'email', 'asunto', 'mensaje')
    readonly_fields = ('fecha_envio',) # fecha_lectura NO será readonly para poderla actualizar

    # Campo personalizado para mostrar en la vista de detalle del admin
    fieldsets = (
        (None, {
            'fields': ('nombre', 'email', 'asunto', 'mensaje')
        }),
        ('Información del Mensaje', {
            'fields': ('fecha_envio', 'leido', 'fecha_lectura') # Mostrar 'leido' y 'fecha_lectura'
        }),
    )

    def save_model(self, request, obj, form, change):
        # Si se marca como leído Y aún no tiene fecha_lectura o no estaba marcado como leído antes
        if obj.leido and not obj.fecha_lectura:
            obj.fecha_lectura = timezone.now() # Guarda la fecha y hora actuales
        # Si se desmarca como leído, limpia la fecha_lectura (opcional, pero buena práctica)
        elif not obj.leido and obj.fecha_lectura:
            obj.fecha_lectura = None
        super().save_model(request, obj, form, change)

    # --- Acciones personalizadas actualizadas ---
    def marcar_como_leido(self, request, queryset):
        for mensaje in queryset:
            if not mensaje.leido: # Solo actualiza si no estaba ya leído
                mensaje.leido = True
                mensaje.fecha_lectura = timezone.now()
                mensaje.save() # Guardar cada objeto individualmente
        self.message_user(request, "Los mensajes seleccionados han sido marcados como leídos y su fecha de lectura actualizada.")
    marcar_como_leido.short_description = "Marcar mensajes seleccionados como leídos"

    def marcar_como_no_leido(self, request, queryset):
        queryset.update(leido=False, fecha_lectura=None) # Al desmarcar, también limpia la fecha de lectura
        self.message_user(request, "Los mensajes seleccionados han sido marcados como NO leídos y su fecha de lectura eliminada.")
    marcar_como_no_leido.short_description = "Marcar mensajes seleccionados como NO leídos"


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'activa', 'fecha_inicio', 'fecha_fin', 'url_destino')
    list_filter = ('activa', 'fecha_inicio', 'fecha_fin')
    search_fields = ('titulo', 'mensaje')
    fieldsets = (
        (None, {
            'fields': ('titulo', 'mensaje', 'activa', 'imagen', 'url_destino')
        }),
        ('Fechas de Vigencia', {
            'fields': ('fecha_inicio', 'fecha_fin'),
            'classes': ('collapse',), # Esto colapsa la sección por defecto
        }),
    )

# --- REGISTROS DE MODELOS CON SUS CLASES ADMIN PERSONALIZADAS ---
admin.site.register(Customer, CustomerAdmin)
#admin.site.register(Product, ProductAdmin) # ¡REGISTRAR Product con ProductAdmin modificado!
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(ShippingAddress, ShippingAddressAdmin)

# --- NUEVOS REGISTROS PARA CATEGORÍAS ---
admin.site.register(Category, CategoryAdmin)
admin.site.register(SubCategory, SubCategoryAdmin)