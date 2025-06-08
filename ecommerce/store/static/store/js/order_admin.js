function updateCartTotal() {
    let total = 0;

    const rows = document.querySelectorAll('.dynamic-orderitem_set'); // default name by Django
    rows.forEach(row => {
        const qtyInput = row.querySelector('[name$="-quantity"]');
        const productSelect = row.querySelector('[name$="-product"]');

        const priceMap = window.productPrices || {};

        if (qtyInput && productSelect) {
            const qty = parseInt(qtyInput.value || 0);
            const productId = productSelect.value;
            const price = parseFloat(priceMap[productId] || 0);

            total += qty * price;
        }
    });

    const display = document.getElementById('cart-total-display');
    if (display) {
        display.innerText = total.toFixed(2);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Define prices (inject them from the server ideally)
    window.productPrices = JSON.parse(document.getElementById('product-price-data').textContent);

    // Initial total
    updateCartTotal();

    // Add event listeners
    document.body.addEventListener('change', function (e) {
        if (e.target.matches('[name$="-quantity"], [name$="-product"]')) {
            updateCartTotal();
        }
    });
});
