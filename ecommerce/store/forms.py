# store/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User  # Aunque get_user_model es preferible, se mantiene si ya lo usas.
from .models import Customer  # Necesario para el ProfileEditForm


class CustomUserCreationForm(UserCreationForm):
    # Puedes añadir campos adicionales si lo necesitas, por ejemplo, email
    email = forms.EmailField(required=True)  # Hacemos el email obligatorio

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = UserCreationForm.Meta.fields + ('email',)  # Añadimos 'email' a los campos
        # Si quisieras más campos fields = ('username', 'email', 'first_name', 'last_name',)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = UserChangeForm.Meta.fields


class UserCreationFormWithEmail(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Requerido, 254 caracteres como máximo y debe ser válido.")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo electrónico.")
        return email


# --- NUEVO: Formulario para la edición del perfil de usuario ---
class ProfileEditForm(forms.ModelForm):
    # Campos que corresponden al modelo User
    username = forms.CharField(max_length=150, required=True, label="Nombre de Usuario")
    email = forms.EmailField(required=True, label="Email")

    # Campos que corresponden al modelo Customer (como el nombre personal)
    customer_name = forms.CharField(max_length=200, required=True, label="Nombre Completo")

    class Meta:
        model = User  # El formulario se asocia principalmente al modelo User para username y email
        fields = ['username', 'email']  # Estos campos se mapearán directamente al User

    def __init__(self, *args, **kwargs):
        # Capturamos la instancia de Customer si se pasa para pre-llenar los datos
        self.customer_instance = kwargs.pop('customer_instance', None)
        super().__init__(*args, **kwargs)

        # Pre-llenar el campo 'customer_name' si tenemos una instancia de Customer
        if self.customer_instance:
            self.fields['customer_name'].initial = self.customer_instance.name

        # Añadir clases de Bootstrap al widget de cada campo
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control mb-3'  # Clase para Bootstrap y margen

    def clean_username(self):
        username = self.cleaned_data['username']
        # Si el username ha cambiado Y ya existe otro usuario con ese username
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso. Por favor, elige otro.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        # Si el email ha cambiado Y ya existe otro usuario con ese email (excluyendo al usuario actual)
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este email ya está registrado. Por favor, usa otro.")
        return email

    def save(self, commit=True):
        # Primero, guarda los cambios en el modelo User
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()

        # Luego, guarda los cambios en el modelo Customer
        if self.customer_instance:
            self.customer_instance.name = self.cleaned_data['customer_name']
            self.customer_instance.email = self.cleaned_data['email']  # Asegura consistencia con User.email
            if commit:
                self.customer_instance.save()

        return user
