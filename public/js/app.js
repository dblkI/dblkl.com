document.addEventListener('DOMContentLoaded', () => {
    // 1. Navegación de tarjetas
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('click', () => {
            const projectType = card.getAttribute('data-project');
            window.location.href = `./${projectType}/`;
        });
    });

    // 2. Intento de saludo dinámico
    updateGreeting();
});

async function updateGreeting() {
    const greetingElement = document.getElementById('greeting-text');
    // IMPORTANTE: Cambiaremos esta URL por la que te dé la terminal tras el deploy exitoso
    const FUNCTION_URL = 'https://us-central1-prod-main-website.cloudfunctions.net/helloWorld?name=Daniel';

    try {
        const response = await fetch(FUNCTION_URL);
        if (response.ok) {
            const data = await response.json();
            greetingElement.textContent = data.message;
        }
    } catch (error) {
        // Si falla (porque aún no hay deploy), mantenemos el texto original
        console.log("Nota: Esperando despliegue de Cloud Function...");
    }
}