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
# ecommerce/store/views.py

# Asegúrate de que todas tus importaciones estén presentes, incluyendo json, datetime, Decimal, uuid y transaction
import json
import datetime
import uuid
from decimal import Decimal
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Order, Customer, ShippingAddress # Asegúrate de que Product y OrderItem también estén importados
from .utils import guestOrder # Asegúrate de que guestOrder esté importado

@csrf_exempt
def processOrder(request):
    # Genera un ID de transacción basado en el timestamp.
    # En un entorno real con PayPal, este ID debería provenir de la respuesta de PayPal.
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    customer = None
    order = None

    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
    else:
        # Aquí se gestiona el pedido para usuarios no registrados.
        # guestOrder crea o recupera un Customer basado en la sesión/dispositivo y crea la Order.
        customer, order = guestOrder(request, data)

    # --- INICIO DE AJUSTES ---

    # Convertir el total del formulario a Decimal para una comparación precisa.
    try:
        total = Decimal(data['form']['total'])
    except (TypeError, ValueError):
        # Maneja el caso en que el total no es un número válido.
        return JsonResponse({'error': 'Invalid total amount received from form'}, status=400)

    # Verifica si el total del formulario coincide con el total calculado en el backend.
    # Esta es una medida de seguridad crucial para evitar manipulaciones de precios.
    # Usamos .quantize para evitar problemas de precisión con los decimales.
    if total.quantize(Decimal('0.01')) == order.get_cart_total.quantize(Decimal('0.01')):
        order.complete = True
        order.transaction_id = transaction_id # Asigna el ID de transacción solo si la compra es válida.
    else:
        # Si los totales no coinciden, es un problema de seguridad o un error.
        print(f"DEBUG: Comparación de total fallida - Total del formulario: {total} vs Total del carrito: {order.get_cart_total}")
        print(f"DEBUG: Diferencia: {total - order.get_cart_total}")
        # En este caso, NO marcamos la orden como completa y devolvemos un error.
        # Esto previene que una orden con precio manipulado se complete.
        return JsonResponse({'error': 'Total mismatch detected. Order not processed.'}, status=400)

    order.save() # Guarda la orden con el estado 'complete' actualizado y el transaction_id.

    # Guardar la dirección de envío si la orden lo requiere.
    # El @property 'order.shipping' se evaluará aquí.
    if order.shipping: # No es necesario poner '== True', ya que es un booleano.
        ShippingAddress.objects.create(
            customer=customer,
            order=order,
            address=data['shipping']['address'],
            city=data['shipping']['city'],
            state=data['shipping']['state'],
            zipcode=data['shipping']['zipcode'],
        )

    # Gestionar productos digitales y generar tokens de descarga.
    # transaction.atomic() asegura que si algo falla aquí, todos los cambios se revierten.
    with transaction.atomic():
        for item in order.orderitem_set.all():
            if item.product and item.product.has_digital_file: # Asegúrate de comprobar item.product no sea None
                if not item.download_token: # Solo crea token si no existe (normalmente ya lo tendrían por default en el modelo)
                    item.download_token = uuid.uuid4()
                    item.save()

    # --- NUEVO: Almacenar el order_id en la sesión para el usuario invitado ---
    # Esto es crucial para permitir que el invitado vea la página de confirmación.
    if not request.user.is_authenticated:
        request.session['guest_order_id'] = order.id
    # --- FIN NUEVO ---

    # Devuelve una respuesta JSON indicando que el pedido fue procesado.
    # Es importante pasar el order_id para la redirección a la página de confirmación.
    return JsonResponse({'message': 'Order processed successfully', 'order_id': order.id}, status=200)
# @csrf_exempt
# def processOrder(request):
#     transaction_id = datetime.datetime.now().timestamp()
#     data = json.loads(request.body)
#
#     if request.user.is_authenticated:
#         customer = request.user.customer
#         order, created = Order.objects.get_or_create(customer=customer, complete=False)
#     else:
#         customer, order = guestOrder(request, data)
#
#     # --- CAMBIO AQUÍ: Convertir el total del formulario a Decimal ---
#     # Es crucial que compares Decimal con Decimal
#     try:
#         total = Decimal(data['form']['total']) # Convierte a Decimal
#     except (TypeError, ValueError):
#         # Maneja el caso en que el total no es un número válido
#         return JsonResponse({'error': 'Invalid total amount'}, status=400)
#
#     order.transaction_id = transaction_id
#
#     if total.quantize(Decimal('0.01')) == order.get_cart_total.quantize(Decimal('0.01')):
#         order.complete = True
#     else:
#         # Esto es importante para depurar si la comparación falla
#         print(f"DEBUG: Comparison failed - Form Total: {total} (Type: {type(total)}) vs Cart Total: {order.get_cart_total} (Type: {type(order.get_cart_total)})")
#         print(f"DEBUG: Difference: {total - order.get_cart_total}")
#         # Si la comparación falla, quizás quieras registrarlo o marcar la orden para revisión
#         # order.complete = False # o mantenerlo como False si no se marcó antes
#         # Puedes añadir un manejo de errores más sofisticado aquí
#         pass # La orden permanecerá como complete=False si la comparación falla
#
#     order.save() # Guarda la orden con el estado 'complete' actualizado
#
#     if order.shipping == True: # Ojo: order.shipping es un @property. Se evaluará al momento.
#         ShippingAddress.objects.create(
#             customer=customer,
#             order=order,
#             address=data['shipping']['address'],
#             city=data['shipping']['city'],
#             state=data['shipping']['state'],
#             zipcode=data['shipping']['zipcode'],
#         )
#
#     with transaction.atomic():
#         for item in order.orderitem_set.all():
#             if item.product.has_digital_file:
#                 if not item.download_token: # Solo crea token si no existe
#                     item.download_token = uuid.uuid4()
#                     item.save()
#
#     return JsonResponse({'message': 'Order processed', 'order_id': order.id}, safe=False)




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
