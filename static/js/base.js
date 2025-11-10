// Base.js - Handles sidebar toggle and navigation functionality

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    
    // Initialize
    initSidebar();
    initNavigation();
    
    /**
     * Initialize sidebar toggle functionality
     */
    function initSidebar() {
        if (!menuToggle || !sidebar) return;
        
        // Load saved sidebar state from localStorage
        const sidebarState = localStorage.getItem('sidebarCollapsed');
        if (sidebarState === 'true') {
            sidebar.classList.add('collapsed');
        }
        
        // Toggle sidebar on button click
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            
            // Save state to localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
            
            // Animate hamburger icon
            animateHamburger(isCollapsed);
        });
    }
    
    /**
     * Animate hamburger icon
     */
    function animateHamburger(isCollapsed) {
        const hamburger = document.querySelector('.hamburger-icon');
        if (!hamburger) return;
        
        if (isCollapsed) {
            hamburger.style.transform = 'rotate(180deg)';
        } else {
            hamburger.style.transform = 'rotate(0deg)';
        }
    }
    
    /**
     * Initialize navigation functionality
     */
    function initNavigation() {
        // Get current page path
        const currentPath = window.location.pathname;
        
        // Highlight active navigation items (both desktop and mobile)
        const navLinks = document.querySelectorAll('.nav-link, .mobile-nav-link');
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            
            // Check if link matches current path
            if (href && href !== '#' && currentPath.includes(href)) {
                link.classList.add('active');
            }
            
            // Add click event for future navigation
            link.addEventListener('click', function(e) {
                const targetHref = this.getAttribute('href');
                
                // If href is '#', prevent default (placeholder)
                if (targetHref === '#') {
                    e.preventDefault();
                    console.log('Navigation item clicked:', this.querySelector('.nav-text, .mobile-nav-text')?.textContent);
                    return;
                }
                
                // Remove active class from all links
                navLinks.forEach(l => l.classList.remove('active'));
                
                // Add active class to clicked link
                this.classList.add('active');
            });
        });
    }
    
    /**
     * Handle responsive behavior on window resize
     */
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            handleResponsive();
        }, 250);
    });
    
    /**
     * Handle responsive layout changes
     */
    function handleResponsive() {
        const width = window.innerWidth;
        
        // Tablet breakpoint: auto-collapse sidebar
        if (width >= 769 && width <= 1024) {
            if (!sidebar.classList.contains('collapsed')) {
                sidebar.classList.add('collapsed');
                localStorage.setItem('sidebarCollapsed', 'true');
            }
        }
    }
    
    /**
     * Add smooth scroll behavior for in-page navigation
     */
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            e.preventDefault();
            const target = document.querySelector(href);
            
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    /**
     * Handle keyboard navigation
     */
    document.addEventListener('keydown', function(e) {
        // Toggle sidebar with Ctrl/Cmd + B
        if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
            e.preventDefault();
            if (menuToggle && sidebar) {
                menuToggle.click();
            }
        }
    });
    
    /**
     * Add ripple effect to navigation items (optional enhancement)
     */
    function addRippleEffect(element, e) {
        const ripple = document.createElement('span');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        
        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = x + 'px';
        ripple.style.top = y + 'px';
        ripple.classList.add('ripple');
        
        element.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
        }, 600);
    }
    
    // Add ripple effect to navigation links
    const allNavLinks = document.querySelectorAll('.nav-link, .mobile-nav-link');
    allNavLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            addRippleEffect(this, e);
        });
    });
    
    /**
     * Handle mobile menu behavior
     */
    if (window.innerWidth <= 768) {
        // Hide mobile nav on scroll down, show on scroll up
        let lastScrollTop = 0;
        const mobileNav = document.querySelector('.mobile-nav');
        
        window.addEventListener('scroll', function() {
            if (!mobileNav) return;
            
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (scrollTop > lastScrollTop && scrollTop > 100) {
                // Scrolling down
                mobileNav.style.transform = 'translateY(100%)';
            } else {
                // Scrolling up
                mobileNav.style.transform = 'translateY(0)';
            }
            
            lastScrollTop = scrollTop;
        });
    }
});

// Add CSS for ripple effect dynamically
const style = document.createElement('style');
style.textContent = `
    .nav-link, .mobile-nav-link {
        position: relative;
        overflow: hidden;
    }
    
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(40, 167, 69, 0.3);
        transform: scale(0);
        animation: ripple-animation 0.6s ease-out;
        pointer-events: none;
    }
    
    @keyframes ripple-animation {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
