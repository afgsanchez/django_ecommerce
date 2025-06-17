from .models import Category, SubCategory  # Importa tus modelos de categoría


def categories_menu(request):
    """
    Context processor para añadir las categorías y subcategorías
    al contexto de todas las plantillas.
    """
    all_categories = Category.objects.all().order_by('name')

    # Intenta determinar la categoría y subcategoría seleccionada de la URL actual
    selected_category_slug = request.resolver_match.kwargs.get('category_slug')
    selected_subcategory_slug = request.resolver_match.kwargs.get('subcategory_slug')

    selected_category_obj = None
    selected_subcategory_obj = None

    if selected_category_slug:
        try:
            selected_category_obj = Category.objects.get(slug=selected_category_slug)
        except Category.DoesNotExist:
            pass  # No hacer nada si la categoría no existe

    if selected_subcategory_slug:
        try:
            selected_subcategory_obj = SubCategory.objects.get(slug=subcategory_slug,
                                                               category__slug=selected_category_slug)
        except SubCategory.DoesNotExist:
            pass  # No hacer nada si la subcategoría no existe

    return {
        'all_categories': all_categories,  # Todas las categorías para el menú principal
        'selected_category_obj': selected_category_obj,  # La categoría que está activa
        'selected_subcategory_obj': selected_subcategory_obj,  # La subcategoría que está activa
    }
