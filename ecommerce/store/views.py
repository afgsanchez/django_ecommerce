from django.shortcuts import render, redirect, get_object_or_404
import os
import json
import datetime
import uuid
from django import forms
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse, HttpResponseForbidden, Http404
from django.db import transaction
from django.contrib.auth.decorators import login_required
from wsgiref.util import FileWrapper
from decimal import Decimal
from .forms import CustomUserCreationForm
from .models import Customer, Product, Order, OrderItem, ShippingAddress
from .utils import cookieCart, cartData, guestOrder # <--- ¡Asegúrate de importar guestOrder aquí!
from django.contrib.auth import login
import  re


# -----------------------------------------------------------------------
# VISTAS GENERALES DE LA TIENDA
# -----------------------------------------------------------------------

def store(request):
    data = cartData(request)

    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    products = Product.objects.all()
    context = {'products': products, 'cartItems': cartItems}
    return render(request, 'store/store.html', context)


def cart(request):
    data = cartData(request)

    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/cart.html', context)


def checkout(request):
    data = cartData(request)

    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/checkout.html', context)


def updateItem(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']
    print('Action:', action)
    print('Product:', productId)

    customer = request.user.customer
    product = Product.objects.get(id=productId)
    order, created = Order.objects.get_or_create(customer=customer, complete=False)

    orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

    if action == 'add':
        orderItem.quantity = (orderItem.quantity + 1)
    elif action == 'remove':
        orderItem.quantity = (orderItem.quantity - 1)

    orderItem.save()

    if orderItem.quantity <= 0:
        orderItem.delete()

    return JsonResponse('Item was added', safe=False)

# -----------------------------------------------------------------------
# VISTAS DE AUTENTICACIÓN Y REGISTRO
# -----------------------------------------------------------------------

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            Customer.objects.create(
                user=user,
                name=user.username,
                email=user.email,
            )

            login(request, user)
            return redirect('store')
    else:
        form = CustomUserCreationForm()

    form.fields['username'].widget = forms.TextInput(
        attrs={'class': 'form-control mb-2', 'placeholder': 'Nombre de usuario'})
    form.fields['email'].widget = forms.EmailInput(
        attrs={'class': 'form-control mb-2', 'placeholder': 'Dirección email'})
    form.fields['password1'].widget = forms.PasswordInput(
        attrs={'class': 'form-control mb-2', 'placeholder': 'Contraseña'})
    form.fields['password2'].widget = forms.PasswordInput(
        attrs={'class': 'form-control mb-2', 'placeholder': 'Repita la contraseña'})

    return render(request, 'registration/signup.html', {'form': form})


# -----------------------------------------------------------------------
# VISTAS DE PROCESAMIENTO DE PEDIDO Y DESCARGAS DIGITALES
# -----------------------------------------------------------------------
# @csrf_exempt
# def processOrder(request):
#     transaction_id = datetime.datetime.now().timestamp()
#     data = json.loads(request.body)
#
#     print(f"DEBUG: Datos recibidos (data): {data}") # Mantén este print para depuración
#
#     customer = None
#     order = None
#
#     if request.user.is_authenticated:
#         customer = request.user.customer
#         order, created = Order.objects.get_or_create(customer=customer, complete=False)
#     else:
#         customer, order = guestOrder(request, data)
#
#     try:
#         total = Decimal(data['form']['total'])
#     except (TypeError, ValueError):
#         return JsonResponse({'error': 'Total del formulario inválido'}, status=400)
#
#     user_form_name = data['form'].get('name', '').strip()
#     user_form_email = data['form'].get('email', '').strip()
#
#     shipping_data = data.get('shipping', {})
#
#     print(f"DEBUG: Contenido de shipping_data: {shipping_data} (Tipo: {type(shipping_data)})") # Mantén este print
#
#     # --- CAMBIO CLAVE AQUÍ: Aseguramos que el resultado de .get() sea una cadena antes de .strip() ---
#     address = str(shipping_data.get('address', '') or '').strip()
#     city = str(shipping_data.get('city', '') or '').strip()
#     state = str(shipping_data.get('state', '') or '').strip()
#     zipcode = str(shipping_data.get('zipcode', '') or '').strip()
#     phone_number = str(shipping_data.get('phone_number', '') or '').strip()
#     # --- FIN CAMBIO CLAVE ---
#
#     print(f"DEBUG: Valor de phone_number recibido (después de strip): '{phone_number}'") # Mantén este print
#
#     # 1. Validar nombre y email SIEMPRE
#     if not user_form_name:
#         return JsonResponse({'error': 'El campo "Nombre completo" es obligatorio.'}, status=400)
#     if not user_form_email:
#         return JsonResponse({'error': 'El campo "Email" es obligatorio.'}, status=400)
#
#     # 2. Validar campos de envío y teléfono SOLO SI el pedido requiere envío
#     if order.shipping:
#         required_shipping_fields = {
#             'Dirección': address,
#             'Ciudad': city,
#             'Provincia': state,
#             'Código Postal': zipcode,
#             'Número de Teléfono': phone_number,
#         }
#
#         for field_name, value in required_shipping_fields.items():
#             if not value:
#                 return JsonResponse({'error': f'El campo "{field_name}" es obligatorio para este pedido con envío.'}, status=400)
#
#         # 3. Validar formato del número de teléfono
#         phone_regex = r'^\+?[\d\s-]{7,20}$'
#         print(f"DEBUG: Regex a usar para teléfono: '{phone_regex}'") # Mantén este print
#         print(f"DEBUG: ¿Coincide '{phone_number}' con el regex? {bool(re.fullmatch(phone_regex, phone_number))}") # Mantén este print
#
#         if not re.fullmatch(phone_regex, phone_number):
#             return JsonResponse({'error': 'El "Número de Teléfono" no tiene un formato válido. Debe contener solo números, espacios o guiones, y tener una longitud razonable.'}, status=400)
#
#     # Lógica de comparación de precios y completitud de la orden
#     if total.quantize(Decimal('0.01')) == order.get_cart_total.quantize(Decimal('0.01')):
#         order.complete = True
#         order.transaction_id = transaction_id
#         order.date_ordered = datetime.datetime.now()
#     else:
#         print(f"DEBUG: Comparación de total fallida - Form: {total} vs Cart: {order.get_cart_total}")
#         return JsonResponse({'error': 'Error de precios: El total no coincide. Pedido no procesado.'}, status=400)
#
#     order.save()
#
#     # Creación de ShippingAddress solo si el pedido requiere envío
#     if order.shipping:
#         ShippingAddress.objects.create(
#             customer=customer,
#             order=order,
#             address=address,
#             city=city,
#             state=state,
#             zipcode=zipcode,
#             phone_number=phone_number,
#         )
#
#     with transaction.atomic():
#         for item in order.orderitem_set.all():
#             if item.product and item.product.has_digital_file:
#                 if not item.download_token:
#                     item.download_token = uuid.uuid4()
#                     item.save()
#
#     if not request.user.is_authenticated:
#         request.session['guest_order_id'] = order.id
#
#     return JsonResponse({'message': 'Pedido procesado con éxito', 'order_id': order.id}, status=200)
#
#

@csrf_exempt
def processOrder(request):
    data = json.loads(request.body)

    print(f"DEBUG: Datos recibidos (data) para VALIDACIÓN: {data}")

    customer = None
    order = None

    if request.user.is_authenticated:
        customer = request.user.customer
        # Obtener o crear una orden incompleta para este cliente
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
    else:
        # Para invitados, crear una orden temporal (que se guardará en sesión en guestOrder)
        # Esta orden NO ESTÁ COMPLETA aún.
        customer, order = guestOrder(request, data)

    # Validar el total del formulario con el total del carrito de la orden
    try:
        form_total = Decimal(data['form']['total'])
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Total del formulario inválido'}, status=400)

    # Comparar los totales para prevenir manipulaciones de precios
    if form_total.quantize(Decimal('0.01')) != order.get_cart_total.quantize(Decimal('0.01')):
        print(f"DEBUG: Comparación de total fallida - Form: {form_total} vs Cart: {order.get_cart_total}")
        return JsonResponse({'error': 'Error de precios: El total no coincide. Pedido no procesado.'}, status=400)

    # Recoger y sanear los datos del formulario de usuario y envío
    user_form_name = data['form'].get('name', '').strip()
    user_form_email = data['form'].get('email', '').strip()

    shipping_data = data.get('shipping', {})
    address = str(shipping_data.get('address', '') or '').strip()
    city = str(shipping_data.get('city', '') or '').strip()
    state = str(shipping_data.get('state', '') or '').strip()
    zipcode = str(shipping_data.get('zipcode', '') or '').strip()
    phone_number = str(shipping_data.get('phone_number', '') or '').strip()

    # 1. Validar nombre y email SIEMPRE
    if not user_form_name:
        return JsonResponse({'error': 'El campo "Nombre completo" es obligatorio.'}, status=400)
    if not user_form_email:
        return JsonResponse({'error': 'El campo "Email" es obligatorio.'}, status=400)

    # 2. Validar campos de envío y teléfono SOLO SI el pedido requiere envío
    if order.shipping:
        required_shipping_fields = {
            'Dirección': address,
            'Ciudad': city,
            'Provincia': state,
            'Código Postal': zipcode,
            'Número de Teléfono': phone_number,
        }
        for field_name, value in required_shipping_fields.items():
            if not value:
                return JsonResponse({'error': f'El campo "{field_name}" es obligatorio para este pedido con envío.'}, status=400)

        # 3. Validar formato del número de teléfono
        phone_regex = r'^\+?[\d\s-]{7,20}$'
        if not re.fullmatch(phone_regex, phone_number):
            return JsonResponse({'error': 'El "Número de Teléfono" no tiene un formato válido. Debe contener solo números, espacios o guiones, y tener una longitud razonable.'}, status=400)

    # Si todas las validaciones pasan:
    # Actualizar la información del cliente (nombre, email)
    if customer: # customer siempre debería existir aquí
        customer.name = user_form_name
        customer.email = user_form_email
        customer.save()

    # Crear o actualizar la dirección de envío (si es necesaria)
    if order.shipping:
        # Usa update_or_create para manejar si ya existe una dirección para esta orden incompleta
        ShippingAddress.objects.update_or_create(
            customer=customer,
            order=order,
            defaults={
                'address': address,
                'city': city,
                'state': state,
                'zipcode': zipcode,
                'phone_number': phone_number,
            }
        )

    # En este punto, la orden está validada y los datos iniciales guardados,
    # pero la orden NO está marcada como completa todavía.
    # Devolvemos el order.id para que el frontend pueda usarlo en la fase de completado.
    return JsonResponse({'message': 'Validación de pedido exitosa.', 'order_id': order.id}, status=200)


# NUEVA FUNCIÓN: completeOrder
@csrf_exempt
def completeOrder(request):
    data = json.loads(request.body)
    order_id = data.get('order_id')
    paypal_transaction_id = data.get('paypal_transaction_id')

    if not order_id or not paypal_transaction_id:
        return JsonResponse({'error': 'Faltan datos para finalizar el pedido.'}, status=400)

    try:
        # Obtener la orden que fue validada previamente
        if request.user.is_authenticated:
            customer = request.user.customer
            # Asegura que solo el cliente dueño de la orden pueda completarla
            order = Order.objects.get(id=order_id, customer=customer, complete=False)
        else:
            # Para pedidos de invitados, verifica el ID de la sesión
            guest_order_id_in_session = request.session.get('guest_order_id')
            if str(guest_order_id_in_session) != str(order_id):
                 return JsonResponse({'error': 'Acceso no autorizado a la orden de invitado.'}, status=403)
            order = Order.objects.get(id=order_id, complete=False) # Para invitados, solo el ID es suficiente

    except Order.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado o ya ha sido completado.'}, status=404)

    # Marcar la orden como completa AHORA que el pago ha sido confirmado por PayPal
    order.complete = True
    order.transaction_id = paypal_transaction_id  # Guardar el ID de transacción de PayPal
    order.date_ordered = datetime.datetime.now()
    order.save()

    # Generar tokens de descarga para productos digitales (movido aquí desde processOrder)
    with transaction.atomic():
        for item in order.orderitem_set.all():
            if item.product and item.product.has_digital_file:
                if not item.download_token:
                    item.download_token = uuid.uuid4()
                    item.save()

    # Limpiar el ID de la orden de invitado de la sesión si aplica
    if not request.user.is_authenticated:
        if 'guest_order_id' in request.session:
            del request.session['guest_order_id']

    return JsonResponse({'message': 'Pedido completado con éxito', 'order_id': order.id}, status=200)

# @login_required # <--- ¡ELIMINA O COMENTA ESTA LÍNEA!
def order_complete(request, order_id):
    order = get_object_or_404(Order, id=order_id, complete=True)

    if request.user.is_authenticated:
        customer = request.user.customer
        if order.customer != customer:
            raise Http404("No tienes permiso para ver este pedido.")
        # --- ELIMINA ESTA LÍNEA SI ESTÁ PRESENTE ---
        # if 'guest_order_id' in request.session:
        #     del request.session['guest_order_id']
        # --- FIN DE ELIMINACIÓN ---
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')

        if order.id != guest_order_id_in_session:
            return redirect('store')  # O raise Http404("Acceso no autorizado para tu sesión.")

        # --- ELIMINA ESTA LÍNEA SI ESTÁ PRESENTE ---
        # if 'guest_order_id' in request.session:
        #     del request.session['guest_order_id']
        # --- FIN DE ELIMINACIÓN ---

    digital_order_items = []
    for item in order.orderitem_set.all():
        # Asegúrate de que el producto exista antes de acceder a has_digital_file
        if item.product and item.product.has_digital_file:
            digital_order_items.append(item)

    context = {
        'order': order,
        'digital_order_items': digital_order_items,
    }
    return render(request, 'store/order_complete.html', context)


# --- NUEVA VISTA PARA IMPRIMIR PEDIDO/FACTURA ---

# @login_required # <--- ¡ELIMINA O COMENTA ESTA LÍNEA!
def order_print_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, complete=True) # Asegúrate de que la orden esté completa

    if request.user.is_authenticated:
        # Usuario autenticado: solo puede ver sus propias órdenes
        customer = request.user.customer
        if order.customer != customer:
            raise Http404("No tienes permiso para ver este pedido.")
    else:
        # Usuario no autenticado (invitado):
        # Permite acceso solo si el order_id coincide con el de su sesión actual
        guest_order_id_in_session = request.session.get('guest_order_id')
        if order.id != guest_order_id_in_session:
            # Si no coincide, redirigir o denegar acceso
            return redirect('store') # O raise Http404("Acceso no autorizado.")

    current_datetime = datetime.datetime.now()

    context = {
        'order': order,
        'order_items': order.orderitem_set.all(), # Asumo que obtienes los order_items así
        'current_datetime': current_datetime,
    }
    return render(request, 'store/order_print.html', context)
# @login_required
# def order_print_view(request, order_id):
#     customer = request.user.customer
#     # Asegurarse de que la orden esté completa y pertenezca al usuario
#     order = get_object_or_404(Order, id=order_id, customer=customer, complete=True)
#     order_items = order.orderitem_set.all()
#
#     current_datetime = datetime.datetime.now()
#
#     context = {
#         'order': order,
#         'order_items': order_items,
#         'current_datetime': current_datetime,
#         # Puedes añadir más información aquí si tu "factura" lo requiere (ej. datos de la tienda)
#     }
#     return render(request, 'store/order_print.html', context) # Renderiza el nuevo template

# @login_required # <--- ¡ELIMINA O COMENTA ESTA LÍNEA!
def download_file(request, token):
    try:
        # Ya NO filtramos por product__has_digital_file aquí.
        # Solo comprobamos que la orden esté completa.
        order_item = get_object_or_404(
            OrderItem,
            download_token=token,
            order__complete=True,
        )
    except Http404:
        raise Http404("Archivo no disponible o token inválido.")
    except Exception as e:
        return JsonResponse({'error': f'Error al buscar el archivo: {e}'}, status=500)

    # --- NUEVA COMPROBACIÓN AQUÍ (después de obtener el order_item) ---
    # Asegúrate de que el producto existe y es digital
    if not order_item.product or not order_item.product.has_digital_file:
        return HttpResponseForbidden("Este producto no es digital o el archivo no está disponible.")
    # --- FIN NUEVA COMPROBACIÓN ---

    # --- Comprobación de seguridad para usuarios autenticados y no autenticados ---
    if request.user.is_authenticated:
        if order_item.order.customer != request.user.customer:
            return HttpResponseForbidden("No tienes permiso para descargar este archivo.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        if order_item.order.id != guest_order_id_in_session:
            return HttpResponseForbidden("Acceso no autorizado para esta descarga.")

    if not order_item.product.digital_file:
        return HttpResponseForbidden("El archivo digital no está adjunto al producto.")

    file_path = order_item.product.digital_file.path
    file_name = order_item.product.digital_file.name.split('/')[-1]

    try:
        if not os.path.exists(file_path):
            return JsonResponse({'error': 'El archivo físico no se encontró en el servidor.'}, status=404)

        wrapper = FileWrapper(open(file_path, 'rb'))
        response = FileResponse(wrapper, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response['Content-Length'] = order_item.product.digital_file.size

        return response
    except FileNotFoundError:
        return JsonResponse({'error': 'File not found on server'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error al servir el archivo: {e}'}, status=500)

# @login_required
# def download_file(request, token):
#     order_item = get_object_or_404(OrderItem, download_token=token)
#
#     if request.user.customer != order_item.order.customer:
#         return HttpResponseForbidden("No tienes permiso para descargar este archivo.")
#
#     if not order_item.product.has_digital_file or not order_item.order.complete:
#         return HttpResponseForbidden("Archivo no disponible o pedido incompleto.")
#
#     file_path = order_item.product.digital_file.path
#     file_name = order_item.product.digital_file.name.split('/')[-1]
#
#     try:
#         wrapper = FileWrapper(open(file_path, 'rb'))
#         response = FileResponse(wrapper, content_type='application/octet-stream')
#         response['Content-Disposition'] = f'attachment; filename="{file_name}"'
#         response['Content-Length'] = order_item.product.digital_file.size
#
#         return response
#     except FileNotFoundError:
#         return JsonResponse({'error': 'File not found'}, status=404)
#     except Exception as e:
#         return JsonResponse({'error': f'Error serving file: {e}'}, status=500)
