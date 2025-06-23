from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),
    path('store/', views.store, name="store"),
    path('cart/', views.cart, name="cart"),
    path('checkout/', views.checkout, name="checkout"),
    path('update_item/', views.updateItem, name="update_item"),
    path('process_order/', views.processOrder, name="process_order"),
    path('complete_order/', views.completeOrder, name="complete_order"),
    path('signup/', views.signup, name='signup'),
    path('order_complete/<int:order_id>/', views.order_complete, name='order_complete'),
    path('order_print/<int:order_id>/', views.order_print_view, name='order_print'), # Nombre de la ruta: 'order_print'
    path('download_file/<uuid:token>/', views.download_file, name='download_file'), # Nombre de la ruta: 'download_file'
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    # Ruta para productos por categoría: /store/electronica/
    path('category/<slug:category_slug>/', views.store, name='products_by_category'),
    # Ruta para productos por subcategoría: /store/electronica/smartphones/
    path('category/<slug:category_slug>/<slug:subcategory_slug>/', views.store, name='products_by_subcategory'),
    path('contact/', views.contact_view, name='contact'), # Nueva URL de contacto
]