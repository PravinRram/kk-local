// Mobile navigation toggle
function toggleMobileNav() {
    const navbar = document.querySelector('.navbar-vertical');
    const overlay = document.getElementById('mobileOverlay');
    const hamburger = document.getElementById('hamburgerBtn');
    
    if (!navbar || !overlay || !hamburger) {
        console.error('Navigation elements not found');
        return;
    }
    
    navbar.classList.toggle('show');
    overlay.classList.toggle('show');
    
    if (navbar.classList.contains('show')) {
        hamburger.querySelector('.material-symbols-outlined').textContent = 'close';
    } else {
        hamburger.querySelector('.material-symbols-outlined').textContent = 'menu';
    }
}

// Initialize navigation when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Setup hamburger button click
    const hamburger = document.getElementById('hamburgerBtn');
    if (hamburger) {
        hamburger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleMobileNav();
        });
    }
    
    // Close mobile nav when clicking overlay
    const overlay = document.getElementById('mobileOverlay');
    if (overlay) {
        overlay.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleMobileNav();
        });
    }

    // Handle navbar overflow for dropdown
    const accountButton = document.querySelector('.account-button');
    const navbar = document.querySelector('.navbar-vertical');

    if (accountButton && navbar) {
        accountButton.addEventListener('show.bs.dropdown', function () {
            navbar.style.overflowY = 'visible';
        });
        
        accountButton.addEventListener('hide.bs.dropdown', function () {
            navbar.style.overflowY = 'auto';
        });
    }
});