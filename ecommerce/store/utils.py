import json
import uuid # Necesario para generar IDs únicos para dispositivos
from decimal import Decimal # Para manejar números decimales con precisión

from django.core.exceptions import ObjectDoesNotExist # Para manejar errores cuando un objeto no se encuentra
from .models import Product, Order, OrderItem, Customer # Asegúrate de que todos estos modelos estén importados

def cookieCart(request):
    """
    Función para obtener los datos del carrito de la cookie del navegador.
    Maneja el caso de que la cookie no exista o esté corrupta.
    """
    try:
        cart = json.loads(request.COOKIES.get('cart', '{}'))
    except json.JSONDecodeError:
        # Si la cookie 'cart' no es un JSON válido, se inicializa como un diccionario vacío.
        cart = {}

    items = []
    # Inicializa los totales de la orden como objetos Decimal para precisión
    order = {'get_cart_total': Decimal('0.00'), 'get_cart_items': 0, 'shipping': False}
    cartItems = 0

    for product_id, product_data in cart.items():
        try:
            quantity = product_data.get('quantity', 0)
            # Asegúrate de que quantity sea un entero válido
            quantity = int(quantity)

            product = Product.objects.get(id=product_id)

            # Calcula el total del ítem. product.price ya debería ser Decimal.
            total = product.price * Decimal(quantity)

            # Suma al total general de la orden
            order['get_cart_total'] += total
            order['get_cart_items'] += quantity
            cartItems += quantity

            item = {
                'id': product.id,
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'price': product.price,
                    'imageURL': product.imageURL,
                    'digital': product.digital # Asegúrate de que el campo 'digital' esté disponible en tu modelo Product
                },
                'quantity': quantity,
                'get_total': total,
            }
            items.append(item)

            # Determina si la orden requiere envío (si contiene al menos un producto no digital)
            if not product.digital:
                order['shipping'] = True

        except (ObjectDoesNotExist, ValueError) as e:
            # Si el producto no existe o la cantidad no es un número válido, se ignora el ítem.
            print(f"DEBUG: Error al procesar ítem en cookieCart (ID: {product_id}): {e}. Saltando este ítem.")
            continue # Continúa con el siguiente ítem en el carrito de la cookie

    return {'cartItems': cartItems, 'order': order, 'items': items}


def cartData(request):
    """
    Función principal para obtener los datos del carrito, diferenciando
    entre usuarios autenticados y no autenticados.
    """
    if request.user.is_authenticated:
        # Lógica para usuarios autenticados
        customer, created_customer = Customer.objects.get_or_create(user=request.user)
        if created_customer:
            # Si el cliente fue recién creado, inicializa su nombre y email desde el usuario de Django
            customer.name = request.user.username # O request.user.get_full_name() si lo usas
            customer.email = request.user.email
            customer.save()
            print(f"DEBUG: cartData - Cliente creado para usuario autenticado: {customer.id}")

        order, created_order = Order.objects.get_or_create(customer=customer, complete=False)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items # Asume que Order tiene un @property get_cart_items
    else:
        # Lógica para usuario no autenticado (desde cookies)
        cookieData = cookieCart(request)
        cartItems = cookieData['cartItems']
        order = cookieData['order']
        items = cookieData['items']

    return {'cartItems': cartItems, 'order': order, 'items': items}


def guestOrder(request, data):
    """
    Gestiona la creación o recuperación de un Customer y una Order para usuarios invitados.
    Asegura la reutilización de la Order incompleta para el mismo dispositivo.
    """
    name = data['form'].get('name', '').strip() # Obtener nombre del formulario
    email = data['form'].get('email', '').strip() # Obtener email del formulario

    # Obtener o crear un ID de dispositivo único para el usuario invitado
    device = request.COOKIES.get('device')
    if not device:
        device = str(uuid.uuid4())
        # La cookie 'device' se establecerá en la respuesta HTTP por un middleware o en la vista.
        print(f"DEBUG: guestOrder - Nuevo ID de dispositivo generado: {device}")

    print(f"DEBUG: guestOrder - ID de dispositivo: {device}")

    # Obtener o crear el objeto Customer basado en el ID de dispositivo.
    # Si ya existe un cliente con este dispositivo, se reutiliza.
    customer, created_customer = Customer.objects.get_or_create(device=device)
    print(f"DEBUG: guestOrder - Objeto Customer: ID {customer.id}, Creado: {created_customer}")

    # Actualizar nombre y email del Customer con los datos del formulario.
    # Esto es crucial para que los datos del formulario se asocien con el cliente invitado.
    if customer.name != name or customer.email != email: # Solo guarda si hay cambios
        customer.name = name
        customer.email = email
        customer.save()
        print(f"DEBUG: guestOrder - Datos de Customer {customer.id} actualizados: {name}, {email}")


    # CRUCIAL: Intentar obtener una ORDEN INCOMPLETA existente para este cliente/dispositivo.
    # Si existe, se reutiliza. Si no, se crea una nueva orden incompleta.
    # Esto previene la duplicación de órdenes incompletas si el usuario invitado refresca la página
    # o intenta el checkout varias veces antes de completar el pago.
    order, created_order = Order.objects.get_or_create(customer=customer, complete=False)
    print(f"DEBUG: guestOrder - Objeto Order: ID {order.id}, Creado: {created_order}, Completa: {order.complete}")

    # Sincronizar los ítems del carrito de la cookie con los OrderItems de esta orden incompleta.
    # Esto asegura que la orden en la BD refleje lo que el usuario tiene en su carrito de la cookie.
    cookie_items = cookieCart(request)['items']

    # Crear/actualizar OrderItems basados en el carrito de la cookie
    for item_data in cookie_items:
        product = Product.objects.get(id=item_data['product']['id'])
        orderItem, created_order_item = OrderItem.objects.update_or_create(
            order=order,
            product=product,
            defaults={'quantity': item_data['quantity']} # Siempre actualiza la cantidad
        )
        print(f"DEBUG: guestOrder - OrderItem para Product {product.id}: ID {orderItem.id}, Cantidad: {orderItem.quantity}, Creado: {created_order_item}")

    # Opcional: Eliminar OrderItems de la BD que ya no están en el carrito de la cookie
    # Esto limpia la orden si el usuario eliminó ítems de su carrito.
    product_ids_in_cookie = [item['product']['id'] for item in cookie_items]
    OrderItem.objects.filter(order=order).exclude(product__id__in=product_ids_in_cookie).delete()
    print(f"DEBUG: guestOrder - OrderItems de la orden {order.id} sincronizados con la cookie.")


    return customer, order