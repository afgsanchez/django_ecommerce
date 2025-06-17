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
from .utils import cookieCart, cartData, guestOrder
from django.contrib.auth import login
import re
from django.utils import timezone


# --- VISTAS GENERALES DE LA TIENDA ---

def store(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
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


@csrf_exempt
def updateItem(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']
    print('Action:', action)
    print('Product:', productId)

    if request.user.is_authenticated:
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
        return JsonResponse('Item was added/removed (authenticated)', safe=False)
    else:
        return JsonResponse('Item update for anonymous user handled by cookies', safe=False)


# --- VISTAS DE AUTENTICACIÓN Y REGISTRO ---

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


# --- NUEVO FLUJO DE PROCESAMIENTO DE PEDIDOS (VALIDACIÓN Y FINALIZACIÓN) ---

@csrf_exempt
def processOrder(request):
    data = json.loads(request.body)

    print(f"DEBUG: processOrder - Datos recibidos (data) para VALIDACIÓN: {data}")

    customer = None
    order = None

    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        print(f"DEBUG: processOrder - Usuario autenticado. Order ID: {order.id}, Creada: {created}")
    else:
        customer, order = guestOrder(request, data)
        print(f"DEBUG: processOrder - Usuario NO autenticado. Order ID: {order.id}, (de guestOrder)")

    try:
        form_total = Decimal(data['form'].get('total', '0.00'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Total del formulario inválido'}, status=400)

    if form_total.quantize(Decimal('0.01')) != order.get_cart_total.quantize(Decimal('0.01')):
        print(f"DEBUG: processOrder - Comparación de total fallida - Form: {form_total} vs Cart: {order.get_cart_total}")
        return JsonResponse({'error': 'Error de precios: El total no coincide. Pedido no procesado.'}, status=400)

    user_form_name = data['form'].get('name', '').strip()
    user_form_email = data['form'].get('email', '').strip()

    shipping_data = data.get('shipping', {})
    address = str(shipping_data.get('address', '') or '').strip()
    city = str(shipping_data.get('city', '') or '').strip()
    state = str(shipping_data.get('state', '') or '').strip()
    zipcode = str(shipping_data.get('zipcode', '') or '').strip()
    phone_number = str(shipping_data.get('phone_number', '') or '').strip()

    if not user_form_name:
        return JsonResponse({'error': 'El campo "Nombre completo" es obligatorio.'}, status=400)
    if not user_form_email:
        return JsonResponse({'error': 'El campo "Email" es obligatorio.'}, status=400)

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

        phone_regex = r'^\+?[\d\s-]{7,20}$'
        if not re.fullmatch(phone_regex, phone_number):
            return JsonResponse({'error': 'El "Número de Teléfono" no tiene un formato válido. Debe contener solo números, espacios o guiones, y tener una longitud razonable.'}, status=400)

    if customer:
        if customer.name != user_form_name or customer.email != user_form_email:
            customer.name = user_form_name
            customer.email = user_form_email
            customer.save()
            print(f"DEBUG: processOrder - Customer {customer.id} datos actualizados desde formulario.")

    if order.shipping:
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
        print(f"DEBUG: processOrder - ShippingAddress para Order {order.id} creada/actualizada.")

    if not request.user.is_authenticated:
        request.session['guest_order_id'] = str(order.id)
        print(f"DEBUG: processOrder - ID de orden de invitado ({order.id}) establecido en sesión.")

    return JsonResponse({'message': 'Validación de pedido exitosa.', 'order_id': order.id}, status=200)


@csrf_exempt
def completeOrder(request):
    data = json.loads(request.body)
    order_id = data.get('order_id')
    paypal_transaction_id = data.get('paypal_transaction_id')

    print(f"DEBUG: completeOrder - Datos recibidos: order_id={order_id}, paypal_transaction_id={paypal_transaction_id}")

    if not order_id or not paypal_transaction_id:
        return JsonResponse({'error': 'Faltan datos para finalizar el pedido.'}, status=400)

    try:
        order = Order.objects.get(id=order_id, complete=False)
        print(f"DEBUG: completeOrder - Orden {order.id} encontrada y completa=False.")

        if request.user.is_authenticated:
            if order.customer != request.user.customer:
                print(f"DEBUG: completeOrder - ACCESO NO AUTORIZADO (usuario autenticado).")
                return JsonResponse({'error': 'Acceso no autorizado al pedido de usuario registrado.'}, status=403)
        else:
            guest_order_id_in_session = request.session.get('guest_order_id')
            print(f"DEBUG: completeOrder - guest_order_id_in_session: {guest_order_id_in_session}")
            if str(guest_order_id_in_session) != str(order_id):
                print(f"DEBUG: completeOrder - ACCESO NO AUTORIZADO (invitado). ID de sesión no coincide.")
                return JsonResponse({'error': 'Acceso no autorizado a la orden de invitado.'}, status=403)

    except Order.DoesNotExist:
        print(f"DEBUG: completeOrder - Pedido {order_id} no encontrado o ya completado.")
        return JsonResponse({'error': 'Pedido no encontrado o ya ha sido completado.'}, status=404)

    order.complete = True
    order.transaction_id = paypal_transaction_id
    order.date_ordered = timezone.now()
    order.save()
    print(f"DEBUG: completeOrder - Orden {order.id} marcada como completa.")

    with transaction.atomic():
        for item in order.orderitem_set.all():
            if item.product and item.product.has_digital_file:
                if not item.download_token:
                    item.download_token = uuid.uuid4()
                    item.save()
                    print(f"DEBUG: completeOrder - Token de descarga para OrderItem {item.id} generado.")

    # YA NO SE LIMPIA LA SESIÓN AQUÍ. Se mantiene para las vistas post-compra.

    return JsonResponse({'message': 'Pedido completado con éxito', 'order_id': order.id}, status=200)


# --- VISTAS DE CONFIRMACIÓN Y DESCARGA DE PEDIDOS ---

def order_complete(request, order_id):
    order = get_object_or_404(Order, id=order_id, complete=True)

    if request.user.is_authenticated:
        customer = request.user.customer
        if order.customer != customer:
            raise Http404("No tienes permiso para ver este pedido.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        print(f"DEBUG: order_complete - Acceso de invitado. Order ID: {order_id}, Session ID: {guest_order_id_in_session}")

        # La condición de acceso es crucial: si el ID de la URL coincide con el de la sesión
        if str(order.id) != str(guest_order_id_in_session):
            print(f"DEBUG: order_complete - Acceso no autorizado para invitado, ID no coincide.")
            return redirect('store') # Redirige si la validación falla

        # --- ESTE BLOQUE FUE ELIMINADO EN LA VERSIÓN FINAL PARA MANTENER guest_order_id ---
        # if 'guest_order_id' in request.session:
        #     del request.session['guest_order_id']
        #     print(f"DEBUG: order_complete - ID de orden de invitado ({order.id}) limpiado de la sesión.")
        # --- FIN BLOQUE ELIMINADO ---


    digital_order_items = []
    for item in order.orderitem_set.all():
        if item.product and item.product.has_digital_file:
            digital_order_items.append(item)

    context = {
        'order': order,
        'digital_order_items': digital_order_items,
    }
    return render(request, 'store/order_complete.html', context)


def order_print_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, complete=True)

    if request.user.is_authenticated:
        customer = request.user.customer
        if order.customer != customer:
            raise Http404("No tienes permiso para ver este pedido.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        print(f"DEBUG: order_print_view - Acceso de invitado. Order ID: {order_id}, Session ID: {guest_order_id_in_session}")

        if str(order.id) != str(guest_order_id_in_session):
            print(f"DEBUG: order_print_view - Acceso no autorizado para invitado, ID no coincide.")
            return redirect('store')

    current_datetime = timezone.now()

    context = {
        'order': order,
        'order_items': order.orderitem_set.all(),
        'current_datetime': current_datetime,
    }
    return render(request, 'store/order_print.html', context)


def download_file(request, token):
    try:
        order_item = get_object_or_404(
            OrderItem,
            download_token=token,
            order__complete=True,
        )
    except Http404:
        raise Http404("Archivo no disponible o token inválido.")
    except Exception as e:
        return JsonResponse({'error': f'Error al buscar el archivo: {e}'}, status=500)

    if not order_item.product or not order_item.product.has_digital_file:
        return HttpResponseForbidden("Este producto no es digital o el archivo no está disponible.")

    if request.user.is_authenticated:
        if order_item.order.customer != request.user.customer:
            return HttpResponseForbidden("No tienes permiso para descargar este archivo.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        print(f"DEBUG: download_file - Acceso de invitado. Order ID: {order_item.order.id}, Session ID: {guest_order_id_in_session}")
        if str(order_item.order.id) != str(guest_order_id_in_session):
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

@login_required # Solo usuarios autenticados pueden acceder a su perfil
def profile(request):
    customer = request.user.customer
    # Obtener todas las órdenes completadas para este cliente, las más recientes primero
    orders = Order.objects.filter(customer=customer, complete=True).order_by('-date_ordered')

    context = {
        'customer': customer, # Pasa el objeto customer al contexto
        'orders': orders,     # Pasa las órdenes al contexto
    }
    return render(request, 'store/profile.html', context)