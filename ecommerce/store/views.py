from django.shortcuts import render, redirect, get_object_or_404
import json
import datetime
import uuid
from django import forms
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse, HttpResponseForbidden
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

@csrf_exempt
def processOrder(request):
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
    else:
        customer, order = guestOrder(request, data)

    # --- CAMBIO AQUÍ: Convertir el total del formulario a Decimal ---
    # Es crucial que compares Decimal con Decimal
    try:
        total = Decimal(data['form']['total']) # Convierte a Decimal
    except (TypeError, ValueError):
        # Maneja el caso en que el total no es un número válido
        return JsonResponse({'error': 'Invalid total amount'}, status=400)

    order.transaction_id = transaction_id

    # --- CAMBIO AQUÍ: Comparación de Decimales ---
    # Puedes usar una pequeña tolerancia si es estrictamente necesario,
    # pero si ambos son Decimales, la igualdad debería funcionar.
    # Una forma segura es redondear ambos a 2 decimales para la comparación.
    if total.quantize(Decimal('0.01')) == order.get_cart_total.quantize(Decimal('0.01')):
        order.complete = True
    else:
        # Esto es importante para depurar si la comparación falla
        print(f"DEBUG: Comparison failed - Form Total: {total} (Type: {type(total)}) vs Cart Total: {order.get_cart_total} (Type: {type(order.get_cart_total)})")
        print(f"DEBUG: Difference: {total - order.get_cart_total}")
        # Si la comparación falla, quizás quieras registrarlo o marcar la orden para revisión
        # order.complete = False # o mantenerlo como False si no se marcó antes
        # Puedes añadir un manejo de errores más sofisticado aquí
        pass # La orden permanecerá como complete=False si la comparación falla

    order.save() # Guarda la orden con el estado 'complete' actualizado

    if order.shipping == True: # Ojo: order.shipping es un @property. Se evaluará al momento.
        ShippingAddress.objects.create(
            customer=customer,
            order=order,
            address=data['shipping']['address'],
            city=data['shipping']['city'],
            state=data['shipping']['state'],
            zipcode=data['shipping']['zipcode'],
        )

    with transaction.atomic():
        for item in order.orderitem_set.all():
            if item.product.has_digital_file:
                if not item.download_token: # Solo crea token si no existe
                    item.download_token = uuid.uuid4()
                    item.save()

    return JsonResponse({'message': 'Order processed', 'order_id': order.id}, safe=False)


@login_required
def order_complete(request, order_id):
    customer = request.user.customer
    order = get_object_or_404(Order, id=order_id, customer=customer, complete=True)

    digital_order_items = []
    for item in order.orderitem_set.all():
        if item.product.has_digital_file:
            digital_order_items.append(item)

    context = {
        'order': order,
        'digital_order_items': digital_order_items,
    }
    return render(request, 'store/order_complete.html', context)

# --- NUEVA VISTA PARA IMPRIMIR PEDIDO/FACTURA ---
@login_required
def order_print_view(request, order_id):
    customer = request.user.customer
    # Asegurarse de que la orden esté completa y pertenezca al usuario
    order = get_object_or_404(Order, id=order_id, customer=customer, complete=True)
    order_items = order.orderitem_set.all()

    current_datetime = datetime.datetime.now()

    context = {
        'order': order,
        'order_items': order_items,
        'current_datetime': current_datetime,
        # Puedes añadir más información aquí si tu "factura" lo requiere (ej. datos de la tienda)
    }
    return render(request, 'store/order_print.html', context) # Renderiza el nuevo template

@login_required
def download_file(request, token):
    order_item = get_object_or_404(OrderItem, download_token=token)

    if request.user.customer != order_item.order.customer:
        return HttpResponseForbidden("No tienes permiso para descargar este archivo.")

    if not order_item.product.has_digital_file or not order_item.order.complete:
        return HttpResponseForbidden("Archivo no disponible o pedido incompleto.")

    file_path = order_item.product.digital_file.path
    file_name = order_item.product.digital_file.name.split('/')[-1]

    try:
        wrapper = FileWrapper(open(file_path, 'rb'))
        response = FileResponse(wrapper, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response['Content-Length'] = order_item.product.digital_file.size

        return response
    except FileNotFoundError:
        return JsonResponse({'error': 'File not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error serving file: {e}'}, status=500)
