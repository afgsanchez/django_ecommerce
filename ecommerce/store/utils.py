import json
from .models import *


import json
from django.core.exceptions import ObjectDoesNotExist

# store/utils.py

import json
from decimal import Decimal # <--- ¡IMPORTA DECIMAL!
from .models import Product # <--- Asegúrate de que Product esté importado
from django.core.exceptions import ObjectDoesNotExist # <--- Asegúrate de que ObjectDoesNotExist esté importado

def cookieCart(request):
    try:
        cart = json.loads(request.COOKIES.get('cart', '{}'))
    except json.JSONDecodeError:
        cart = {}

    items = []
    # Inicializa get_cart_total como un objeto Decimal
    order = {'get_cart_total': Decimal('0.00'), 'get_cart_items': 0, 'shipping': False}
    cartItems = 0

    for product_id, product_data in cart.items():
        try:
            quantity = product_data.get('quantity', 0)
            # Asegúrate de que quantity sea un entero
            quantity = int(quantity)

            product = Product.objects.get(id=product_id)

            # Convierte product.price a Decimal si no lo es (ya debería serlo si es DecimalField)
            # y realiza la multiplicación. El resultado será un Decimal.
            total = product.price * Decimal(quantity) # Multiplica Decimal por Decimal o int

            # Suma el total (que es un Decimal) al get_cart_total (que también es un Decimal)
            order['get_cart_total'] += total
            order['get_cart_items'] += quantity
            cartItems += quantity

            item = {
                'id': product.id,
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'price': product.price, # Esto es un Decimal
                    'imageURL': product.imageURL,
                },
                'quantity': quantity,
                'digital': product.digital,
                'get_total': total, # Esto también es un Decimal
            }
            items.append(item)

            if not product.digital:
                order['shipping'] = True

        except (ObjectDoesNotExist, ValueError) as e: # Captura también ValueError para int(quantity)
            print(f"Error processing item in cookieCart: {e}") # Para depuración
            continue

    return {'cartItems': cartItems, 'order': order, 'items': items}

# def cookieCart(request):
#     try:
#         cart = json.loads(request.COOKIES.get('cart', '{}'))
#     except json.JSONDecodeError:
#         cart = {}
#
#     items = []
#     order = {'get_cart_total': 0, 'get_cart_items': 0, 'shipping': False}
#     cartItems = 0  # Inicializar contador de items
#
#     for product_id, product_data in cart.items():
#         try:
#             quantity = product_data.get('quantity', 0)
#             product = Product.objects.get(id=product_id)
#
#             total = product.price * quantity
#             order['get_cart_total'] += total
#             order['get_cart_items'] += quantity
#             cartItems += quantity
#
#             item = {
#                 'id': product.id,
#                 'product': {
#                     'id': product.id,
#                     'name': product.name,
#                     'price': product.price,
#                     'imageURL': product.imageURL,
#                 },
#                 'quantity': quantity,
#                 'digital': product.digital,
#                 'get_total': total,
#             }
#             items.append(item)
#
#             if not product.digital:
#                 order['shipping'] = True
#
#         except (ObjectDoesNotExist, ValueError):
#             # El producto no existe o cantidad inválida: ignorar este item
#             continue
#
#     return {'cartItems': cartItems, 'order': order, 'items': items}

# store/utils.py

# Asegúrate de que todas tus importaciones necesarias están aquí arriba
# Por ejemplo:
# from .models import Customer, Product, Order, OrderItem
# from .utils import cookieCart # Si cookieCart está en otro archivo, aunque generalmente está en el mismo utils.py

def cartData(request):
    if request.user.is_authenticated:
        # Lógica para usuarios autenticados
        try:
            # Intenta obtener el objeto Customer asociado al usuario
            customer = request.user.customer
        except Customer.DoesNotExist:
            # Si el Customer no existe para este usuario (por ejemplo, es un usuario antiguo o un superusuario
            # que se creó antes de implementar la lógica de Customer en el registro),
            # lo creamos en este momento.
            customer = Customer.objects.create(
                user=request.user,
                name=request.user.username, # Puedes ajustar esto si tienes un campo 'first_name' en tu User
                email=request.user.email,
            )
            # No es estrictamente necesario llamar a .save() después de .create() ya que create() lo hace.
            # Pero tampoco hace daño si lo pones.

        # A partir de aquí, el objeto 'customer' está garantizado para existir
        # y el resto de tu lógica para usuarios autenticados puede continuar.

        # Buscar el primer pedido incompleto, si no existe, crearlo
        # Simplificado: get_or_create es más idiomático aquí
        order, created = Order.objects.get_or_create(customer=customer, complete=False)


        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
    else:
        # Carrito para usuario no autenticado (desde cookies)
        cookieData = cookieCart(request)
        cartItems = cookieData['cartItems']
        order = cookieData['order']
        items = cookieData['items']

    return {'cartItems': cartItems, 'order': order, 'items': items}


# def cartData(request):
#     if request.user.is_authenticated:
#         customer = request.user.customer
#
#         # Buscar el primer pedido incompleto, si no existe, crearlo
#         order = Order.objects.filter(customer=customer, complete=False).first()
#         if order is None:
#             order = Order.objects.create(customer=customer, complete=False)
#
#         items = order.orderitem_set.all()
#         cartItems = order.get_cart_items
#     else:
#         # Carrito para usuario no autenticado (desde cookies)
#         cookieData = cookieCart(request)
#         cartItems = cookieData['cartItems']
#         order = cookieData['order']
#         items = cookieData['items']
#
#     return {'cartItems': cartItems, 'order': order, 'items': items}


def guestOrder(request, data):
    name = data['form']['name']
    email = data['form']['email']

    cookieData = cookieCart(request)
    items = cookieData['items']

    customer, created = Customer.objects.get_or_create(email=email)

    # ✅ Solo guardar el nombre si está vacío
    if not customer.name:
        customer.name = name
        customer.save()

    order = Order.objects.create(customer=customer, complete=False)

    for item in items:
        product = Product.objects.get(id=item['id'])
        OrderItem.objects.create(
            product=product,
            order=order,
            quantity=item['quantity'],
        )

    return customer, order

