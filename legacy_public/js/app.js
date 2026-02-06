document.addEventListener('DOMContentLoaded', () => {
    console.log("DBLKL | Marca Personal Activa");

    // Animación de entrada para los elementos de navegación
    const items = document.querySelectorAll('.nav-item');
    items.forEach((item, index) => {
        item.style.animationDelay = `${(index + 1) * 0.2}s`;
    });
});