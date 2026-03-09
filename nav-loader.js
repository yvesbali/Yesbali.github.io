(() => {
  const container = document.getElementById('lcdmh-nav-container');
  if (!container) return;

  const navUrl = 'nav.html?v=' + Date.now();

  fetch(navUrl, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }
      return response.text();
    })
    .then((html) => {
      container.innerHTML = html;
      initLCDMHNav();
    })
    .catch((error) => {
      console.error('Navigation non chargée :', error);
      container.innerHTML =
        '<div style="background:#e67e22;color:#fff;padding:1rem;text-align:center;font-family:Arial,sans-serif;">' +
        'Menu temporairement indisponible — <a href="index.html" style="color:#fff;font-weight:bold;">Accueil</a>' +
        '</div>';
    });

  function initLCDMHNav() {
    const nav = document.getElementById('lcdmh-nav');
    if (!nav) return;

    const navLinks = nav.querySelector('#navLinks');
    const menuToggle = nav.querySelector('#menuToggle');
    const pageRaw = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();
    const currentPage = pageRaw.startsWith('index') ? 'index.html' : pageRaw;

    nav.querySelectorAll('a[href]').forEach((link) => {
      const href = (link.getAttribute('href') || '').trim();
      if (!href || href === '#' || href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:')) {
        return;
      }

      const normalizedHref = href.split('?')[0].split('#')[0].toLowerCase();
      if (normalizedHref === currentPage) {
        link.classList.add('active');

        const parentDropdown = link.closest('.has-drop');
        if (parentDropdown) {
          const parentTrigger = parentDropdown.querySelector(':scope > a');
          if (parentTrigger) parentTrigger.classList.add('active');
        }
      }
    });

    if (menuToggle && navLinks) {
      menuToggle.addEventListener('click', (event) => {
        event.stopPropagation();
        const isOpen = navLinks.classList.toggle('active');
        menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });

      document.addEventListener('click', (event) => {
        if (!nav.contains(event.target)) {
          navLinks.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
          nav.querySelectorAll('.has-drop.open').forEach((item) => item.classList.remove('open'));
        }
      });

      window.addEventListener('resize', () => {
        if (window.innerWidth > 1000) {
          navLinks.classList.remove('active');
          menuToggle.setAttribute('aria-expanded', 'false');
          nav.querySelectorAll('.has-drop.open').forEach((item) => item.classList.remove('open'));
        }
      });
    }

    nav.querySelectorAll('.has-drop > a').forEach((trigger) => {
      trigger.addEventListener('click', (event) => {
        if (window.innerWidth > 1000) return;

        event.preventDefault();
        const item = trigger.parentElement;
        const wasOpen = item.classList.contains('open');

        nav.querySelectorAll('.has-drop.open').forEach((dropdownItem) => {
          dropdownItem.classList.remove('open');
        });

        if (!wasOpen) {
          item.classList.add('open');
        }
      });
    });

    nav.querySelectorAll('.dropdown a').forEach((link) => {
      link.addEventListener('click', () => {
        if (navLinks) navLinks.classList.remove('active');
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
        nav.querySelectorAll('.has-drop.open').forEach((item) => item.classList.remove('open'));
      });
    });
  }
})();
