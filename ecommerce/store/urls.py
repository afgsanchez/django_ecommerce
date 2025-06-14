from django.urls import path
from . import views
#from .views import SignUpView

urlpatterns = [
    path('', views.store, name="store"),
    path('cart/', views.cart, name="cart"),
    path('checkout/', views.checkout, name="checkout"),
    path('update_item/', views.updateItem, name='update_item'),
    path('process_order/', views.processOrder, name="process_order"),
    path('complete_order/', views.completeOrder, name="complete_order"), # Nueva ruta para finalizar el pedido
    # path('signup/', SignUpView.as_view(), name='signup'),
    path('signup/', views.signup, name="signup"),
    # --- NUEVAS URLS PARA DESCARGAS ---
    path('order_complete/<int:order_id>/', views.order_complete, name="order_complete"),
    path('download/<uuid:token>/', views.download_file, name="download_file"),
    path('order/<int:order_id>/print/', views.order_print_view, name='order_print_view'),
]