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
from django.contrib import messages  # Importar messages
from wsgiref.util import FileWrapper
from decimal import Decimal
from .forms import CustomUserCreationForm, ProfileEditForm, MensajeForm
from .models import Customer, Product, Order, OrderItem, ShippingAddress, Category, \
    SubCategory, Promocion  # Importar Category y SubCategory
from .utils import cookieCart, cartData, guestOrder
from django.contrib.auth import login
import re
from django.utils import timezone
from datetime import date
from django.db.models import Q
import random


# --- VISTAS GENERALES DE LA TIENDA ---

def home(request):
    return render(request, 'store/home.html')


def store(request, category_slug=None, subcategory_slug=None):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']

    all_products_query = Product.objects.all()  # Consulta inicial de todos los productos
    selected_category = None
    selected_subcategory = None

    # Filtrar por subcategoría o categoría
    if subcategory_slug:
        selected_subcategory = get_object_or_404(SubCategory, slug=subcategory_slug)
        all_products_query = all_products_query.filter(subcategory=selected_subcategory)
        selected_category = selected_subcategory.category
    elif category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        all_products_query = all_products_query.filter(subcategory__category=selected_category)

    # --- Lógica para seleccionar hasta 12 productos aleatorios ---
    # Convertimos el QuerySet a una lista para poder usar random.sample
    # OJO: Si tienes CIENTOS de miles de productos, .all() puede ser lento.
    # Para ese caso, habría que pensar en una estrategia de "OFFSET/LIMIT" con orden aleatorio de base de datos.
    all_available_products = list(all_products_query)

    # Seleccionamos hasta 12 productos aleatorios
    if len(all_available_products) > 12:
        products_to_display = random.sample(all_available_products, 12)
    else:
        products_to_display = all_available_products  # Si hay menos de 12, mostramos todos

    # Obtener todas las categorías y subcategorías para la navegación
    categories = Category.objects.all().order_by('name')
    subcategories = []
    if selected_category:
        subcategories = selected_category.subcategories.all().order_by('name')

    # Lógica para obtener promociones activas
    today = date.today()
    promotions = Promocion.objects.filter(
        activa=True
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=today)
    ).filter(
        Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=today)
    ).order_by('-fecha_inicio')

    context = {
        'products': products_to_display,  # <--- ¡Ahora pasamos esta nueva lista!
        'cartItems': cartItems,
        'selected_category': selected_category,
        'selected_subcategory': selected_subcategory,
        'categories': categories,
        'subcategories': subcategories,
        'promotions': promotions,
    }
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


# --- FLUJO DE PROCESAMIENTO DE PEDIDOS (VALIDACIÓN Y FINALIZACIÓN) ---

@csrf_exempt
def processOrder(request):
    data = json.loads(request.body)
    customer = None
    order = None

    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
    else:
        customer, order = guestOrder(request, data)

    try:
        form_total = Decimal(data['form'].get('total', '0.00'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Total del formulario inválido'}, status=400)

    if form_total.quantize(Decimal('0.01')) != order.get_cart_total.quantize(Decimal('0.01')):
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
                return JsonResponse({'error': f'El campo "{field_name}" es obligatorio para este pedido con envío.'},
                                    status=400)

        phone_regex = r'^\+?[\d\s-]{7,20}$'
        if not re.fullmatch(phone_regex, phone_number):
            return JsonResponse({
                                    'error': 'El "Número de Teléfono" no tiene un formato válido. Debe contener solo números, espacios o guiones, y tener una longitud razonable.'},
                                status=400)

    if customer:
        if customer.name != user_form_name or customer.email != user_form_email:
            customer.name = user_form_name
            customer.email = user_form_email
            customer.save()

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

    if not request.user.is_authenticated:
        request.session['guest_order_id'] = str(order.id)

    return JsonResponse({'message': 'Validación de pedido exitosa.', 'order_id': order.id}, status=200)


@csrf_exempt
def completeOrder(request):
    data = json.loads(request.body)
    order_id = data.get('order_id')
    paypal_transaction_id = data.get('paypal_transaction_id')

    if not order_id or not paypal_transaction_id:
        return JsonResponse({'error': 'Faltan datos para finalizar el pedido.'}, status=400)

    try:
        order = Order.objects.get(id=order_id, complete=False)

        if request.user.is_authenticated:
            if order.customer != request.user.customer:
                return JsonResponse({'error': 'Acceso no autorizado al pedido de usuario registrado.'}, status=403)
        else:
            guest_order_id_in_session = request.session.get('guest_order_id')
            if str(guest_order_id_in_session) != str(order_id):
                return JsonResponse({'error': 'Acceso no autorizado a la orden de invitado.'}, status=403)

    except Order.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado o ya ha sido completado.'}, status=404)

    order.complete = True
    order.transaction_id = paypal_transaction_id
    order.date_ordered = timezone.now()
    order.save()

    guest_token_to_return = None
    if not request.user.is_authenticated:
        if not order.guest_access_token:
            order.guest_access_token = uuid.uuid4()
            order.save()
        guest_token_to_return = str(order.guest_access_token)

    with transaction.atomic():
        for item in order.orderitem_set.all():
            if item.product and item.product.has_digital_file:
                if not item.download_token:
                    item.download_token = uuid.uuid4()
                    item.save()

    return JsonResponse({
        'message': 'Pedido completado con éxito',
        'order_id': order.id,
        'guest_access_token': guest_token_to_return
    }, status=200)


# --- VISTAS DE CONFIRMACIÓN Y DESCARGA DE PEDIDOS ---

def order_complete(request, order_id):
    order = get_object_or_404(Order, id=order_id, complete=True)
    guest_token = request.GET.get('guest_token')

    if request.user.is_authenticated:
        customer = request.user.customer
        if order.customer != customer:
            raise Http404("No tienes permiso para ver este pedido.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        is_valid_by_session = (str(order.id) == str(guest_order_id_in_session))
        is_valid_by_token = False
        if guest_token and order.guest_access_token:
            try:
                is_valid_by_token = (uuid.UUID(guest_token) == order.guest_access_token)
            except ValueError:
                is_valid_by_token = False

        if not is_valid_by_session and not is_valid_by_token:
            return redirect('store')

    digital_order_items = []
    for item in order.orderitem_set.all():
        if item.product and item.product.has_digital_file:
            digital_order_items.append(item)

    context = {
        'order': order,
        'digital_order_items': digital_order_items,
        'guest_access_token': guest_token
    }
    return render(request, 'store/order_complete.html', context)


def order_print_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, complete=True)
    guest_token = request.GET.get('guest_token')

    if request.user.is_authenticated:
        customer = request.user.customer
        if order.customer != customer:
            raise Http404("No tienes permiso para ver este pedido.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        is_valid_by_session = (str(order.id) == str(guest_order_id_in_session))
        is_valid_by_token = False
        if guest_token and order.guest_access_token:
            try:
                is_valid_by_token = (uuid.UUID(guest_token) == order.guest_access_token)
            except ValueError:
                is_valid_by_token = False

        if not is_valid_by_session and not is_valid_by_token:
            return redirect('store')

    current_datetime = timezone.now()

    context = {
        'order': order,
        'order_items': order.orderitem_set.all(),
        'current_datetime': current_datetime,
        'guest_access_token': guest_token
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
        raise Http404("Archivo no disponible o token de descarga inválido.")
    except Exception as e:
        return JsonResponse({'error': f'Error al buscar el archivo: {e}'}, status=500)

    guest_token = request.GET.get('guest_token')

    if not order_item.product or not order_item.product.has_digital_file:
        return HttpResponseForbidden("Este producto no es digital o el archivo no está disponible.")

    if request.user.is_authenticated:
        if order_item.order.customer != request.user.customer:
            return HttpResponseForbidden("No tienes permiso para descargar este archivo.")
    else:
        guest_order_id_in_session = request.session.get('guest_order_id')
        is_valid_by_session = (str(order_item.order.id) == str(guest_order_id_in_session))
        is_valid_by_token = False
        if guest_token and order_item.order.guest_access_token:
            try:
                is_valid_by_token = (uuid.UUID(guest_token) == order_item.order.guest_access_token)
            except ValueError:
                is_valid_by_token = False

        if not is_valid_by_session and not is_valid_by_token:
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


# --- VISTA PARA EL PERFIL DE USUARIO ---
@login_required
def profile(request):
    customer = request.user.customer
    orders = Order.objects.filter(customer=customer, complete=True).order_by('-date_ordered')

    context = {
        'customer': customer,
        'orders': orders,
    }
    return render(request, 'store/profile.html', context)


# --- NUEVA VISTA PARA EDITAR EL PERFIL ---
@login_required
def edit_profile(request):
    user = request.user
    customer = user.customer  # Obtener la instancia de Customer asociada al usuario

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=user, customer_instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Tu perfil ha sido actualizado con éxito!')
            return redirect('profile')  # Redirige al perfil principal
        else:
            messages.error(request, 'Ha ocurrido un error al actualizar tu perfil. Por favor, revisa los datos.')
    else:
        # Pre-llenar el formulario con los datos actuales del usuario y cliente
        form = ProfileEditForm(instance=user, customer_instance=customer, initial={
            'username': user.username,
            'email': user.email,
            'customer_name': customer.name,
        })

    context = {
        'form': form
    }
    return render(request, 'store/edit_profile.html', context)

# store/views.py



def contact_view(request):
    if request.method == 'POST':
        form = MensajeForm(request.POST)
        if form.is_valid():
            form.save()
            # --- AQUÍ AÑADIMOS EL MENSAJE DE ÉXITO ---
            messages.success(request, '¡Gracias! Hemos recibido tu mensaje y nos pondremos en contacto contigo muy pronto.')
            return redirect('contact') # Redirigimos a la misma URL de contacto para que el mensaje se muestre.
                                       # Si rediriges a 'home', el mensaje también se mostrará en 'home'.
                                       # Decide dónde quieres que aparezca la confirmación.
        else:
            # --- Y AQUÍ UN MENSAJE DE ERROR POR SI ALGO FALLA ---
            messages.error(request, 'Hubo un problema al enviar tu mensaje. Por favor, revisa los campos y inténtalo de nuevo.')
    else:
        form = MensajeForm()
    return render(request, 'store/contact.html', {'form': form})



def product_detail(request, product_slug):
    data = cartData(request)  # Función que asumo tienes para el carrito
    cartItems = data['cartItems']

    # Obtener el producto o 404
    product = get_object_or_404(Product, slug=product_slug)

    # Imágenes principales y adicionales
    additional_images = product.additional_images.all().order_by('order')
    all_product_images = []
    if product.image:
        all_product_images.append(product.image)
    for img_obj in additional_images:
        all_product_images.append(img_obj.image)

    # Productos relacionados: por subcategoría o categoría, excluyendo el producto actual
    if product.subcategory:
        related_products = Product.objects.filter(subcategory=product.subcategory).exclude(id=product.id)[:4]
    elif product.category:
        related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    else:
        related_products = Product.objects.none()  # Si no hay categoría ni subcategoría

    context = {
        'product': product,
        'cartItems': cartItems,
        'all_product_images': all_product_images,
        'related_products': related_products,
    }
    return render(request, 'store/product_detail.html', context)
