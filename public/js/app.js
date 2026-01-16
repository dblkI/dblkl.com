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