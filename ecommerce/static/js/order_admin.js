function updateCartTotal() {
    let total = 0;

    // Obtener precios desde el script JSON
    const priceScript = document.getElementById('product-price-data');
    if (!priceScript) return;

    const priceMap = JSON.parse(priceScript.textContent);

    // Iterar sobre las filas de productos
    const rows = document.querySelectorAll('.dynamic-orderitem_set');

    rows.forEach(row => {
        const qtyInput = row.querySelector('[name$="-quantity"]');
        const productSelect = row.querySelector('[name$="-product"]');

        if (qtyInput && productSelect) {
            const qty = parseInt(qtyInput.value || 0);
            const productId = productSelect.value;

            const price = parseFloat(priceMap[productId] || 0);
            total += qty * price;
        }
    });

    // Mostrar el total actualizado
    const totalDisplay = document.getElementById('cart-total-display');
    if (totalDisplay) {
        totalDisplay.innerText = total.toFixed(2);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Recalcula al cargar
    updateCartTotal();

    // Escucha cambios en cantidad o producto
    document.body.addEventListener('change', function (e) {
        if (e.target.name && (e.target.name.endsWith('-quantity') || e.target.name.endsWith('-product'))) {
            updateCartTotal();
        }
    });

    // También actualiza si se agregan nuevas líneas dinámicamente
    document.body.addEventListener('click', function (e) {
        if (e.target && (e.target.classList.contains('add-row') || e.target.closest('.add-row'))) {
            setTimeout(updateCartTotal, 100); // Espera un poco a que se agregue el nuevo row
        }
    });
});
