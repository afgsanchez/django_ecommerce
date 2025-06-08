from django.db import models
from django.contrib.auth.models import User
import uuid # ¡Importa uuid para generar tokens únicos!
from decimal import Decimal

# Create your models here.
class Customer(models.Model):
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, null=True)
    email = models.EmailField(max_length=200, unique=True)

    def __str__(self):
        return self.name if self.name else 'Cliente Anónimo' # Mejorar representación si name es None

class Product(models.Model):
    name = models.CharField(max_length=200)
    # Recomendación: Usar DecimalField para precios para evitar problemas de precisión con floats
    price = models.DecimalField(max_digits=10, decimal_places=2) # Cambiado de FloatField a DecimalField
    digital = models.BooleanField(default=False, null=True, blank=True)
    image = models.ImageField(null=True, blank=True, upload_to='product_images/')
    digital_file = models.FileField(upload_to='digital_products/', null=True, blank=True) # Campo para el archivo descargable

    def __str__(self):
        return self.name

    @property
    def imageURL(self):
        try:
            url = self.image.url
        except ValueError: # Capturar ValueError si no hay archivo (en vez de un 'except' genérico)
            url = ''
        return url

    # Propiedad para verificar si el producto es digital y tiene un archivo asociado
    @property
    def has_digital_file(self):
        return self.digital and bool(self.digital_file) # Usar bool() para verificar que el FileField no está vacío


class Order(models.Model):
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)
    date_ordered = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=100, null=True)

    def __str__(self):
        return str(self.id)

    @property
    def shipping(self):
        shipping = False
        orderitems = self.orderitem_set.all()
        for i in orderitems:
            # Si ALGÚN producto en el pedido NO es digital, se necesita envío
            if not i.product.digital:
                shipping = True
                break # Una vez que encontramos uno que requiere envío, podemos parar
        return shipping

    @property
    def get_cart_total(self):
        orderitems = self.orderitem_set.all()
        # Aquí, si item.get_total ya devuelve un Decimal, la suma también será un Decimal.
        # No necesitas ninguna conversión o comprobación de tipo adicional aquí.
        total = sum([item.get_total for item in orderitems])
        return total

    @property
    def get_cart_items(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.quantity for item in orderitems])
        return total
# class Order(models.Model):
#     customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)
#     date_ordered = models.DateTimeField(auto_now_add=True)
#     complete = models.BooleanField(default=False)
#     transaction_id = models.CharField(max_length=100, null=True)
#
#     def __str__(self):
#         return str(self.id)
#
#
#     @property
#     def shipping(self):
#         shipping = False
#         orderitems = self.orderitem_set.all()
#         for i in orderitems:
#             # Si ALGÚN producto en el pedido NO es digital, se necesita envío
#             if not i.product.digital:
#                 shipping = True
#                 break # Una vez que encontramos uno que requiere envío, podemos parar
#         return shipping
#
#     @property
#     def get_cart_total(self):
#         orderitems = self.orderitem_set.all()
#         total = sum([item.get_total for item in orderitems])
#         # Asegurarse de que el total se devuelve como un Decimal, si price es DecimalField
#         return total if isinstance(total, models.DecimalField) else models.DecimalField(str(total), max_digits=10, decimal_places=2)
#
#
#     @property
#     def get_cart_items(self):
#         orderitems = self.orderitem_set.all()
#         total = sum([item.quantity for item in orderitems])
#         return total

class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=0, null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    # --- ¡AÑADIDO ESTO! Campo para el token de descarga ---
    download_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True, blank=True)
    # Considera añadir campos para control de descargas, por ejemplo:
    # download_count = models.IntegerField(default=0) # Cuántas veces se ha descargado
    # last_download_date = models.DateTimeField(null=True, blank=True) # Última fecha de descarga

    @property
    def get_total(self):
        total = self.product.price * self.quantity
        return total

    def requires_shipping(self):
        return not self.product.digital

    requires_shipping.boolean = True
    requires_shipping.short_description = 'Requires Shipping'

    def __str__(self):
        return f"{self.product.name} x {self.quantity} (Order: {self.order.id})" # Mejorado para claridad

class ShippingAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    address = models.CharField(max_length=200, null=False)
    city = models.CharField(max_length=200, null=False)
    state = models.CharField(max_length=200, null=False)
    zipcode = models.CharField(max_length=200, null=False)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.address