/* Lucho Landing — Minimal JS */

document.addEventListener('DOMContentLoaded', () => {

    // ── Mobile menu toggle ──
    const toggle = document.getElementById('mobileToggle');
    const menu = document.getElementById('mobileMenu');
    if (toggle && menu) {
        toggle.addEventListener('click', () => {
            menu.classList.toggle('hidden');
            toggle.textContent = menu.classList.contains('hidden') ? '☰' : '✕';
        });
        // Close menu when clicking a link
        menu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                menu.classList.add('hidden');
                toggle.textContent = '☰';
            });
        });
    }

    // ── Nav background on scroll ──
    const nav = document.getElementById('nav');
    if (nav) {
        window.addEventListener('scroll', () => {
            nav.classList.toggle('scrolled', window.scrollY > 50);
        });
    }

    // ── WhatsApp floating button pulse ──
    const waBtn = document.querySelector('a[href*="wa.me"]');
    if (waBtn && waBtn.classList.contains('fixed')) {
        waBtn.classList.add('whatsapp-pulse');
    }

    // ── Smooth reveal on scroll (simple) ──
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('section > div > div, .group').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });

});
