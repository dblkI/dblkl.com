document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.card');

    cards.forEach(card => {
        card.addEventListener('click', () => {
            const projectType = card.getAttribute('data-project');
            const path = projectType === 'home' ? '../' : `./${projectType}/`;
            window.location.href = path;
        });
    });
});

// Función para probar la Cloud Function
async function testCloudFunction() {
    try {
        const response = await fetch('TU_URL_DE_LA_FUNCTION?name=Daniel');
        const data = await response.json();
        console.log("Respuesta de GCP:", data.message);
    } catch (error) {
        console.error("Error llamando a la función:", error);
    }
}