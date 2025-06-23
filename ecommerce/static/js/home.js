document.addEventListener('DOMContentLoaded', () => {
  const button = document.querySelector('.btn-enter-store');

  if (!button) return;

  button.style.position = 'relative';
  button.style.overflow = 'hidden';

  // Crear un span para el rastro de luz
  const lightTrail = document.createElement('span');
  lightTrail.style.position = 'absolute';
  lightTrail.style.top = '0';
  lightTrail.style.left = '0';
  lightTrail.style.width = '100%';
  lightTrail.style.height = '100%';
  lightTrail.style.pointerEvents = 'none';
  lightTrail.style.background = 'linear-gradient(90deg, rgba(0,255,255,0.7), rgba(0,255,255,0))';
  lightTrail.style.transform = 'translateX(-100%)';
  lightTrail.style.transition = 'transform 0.3s ease';
  lightTrail.style.borderRadius = '6px';

  button.appendChild(lightTrail);

  button.addEventListener('mousemove', e => {
    const rect = button.getBoundingClientRect();
    const x = e.clientX - rect.left;
    // Mover el gradiente hacia la posición x con un pequeño retraso
    lightTrail.style.transform = `translateX(${x - rect.width}px)`;
  });

  button.addEventListener('mouseleave', () => {
    // Cuando el ratón salga, el rastro vuelve a su posición inicial
    lightTrail.style.transform = 'translateX(-100%)';
  });
});
