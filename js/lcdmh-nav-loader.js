(() => {
  const container = document.getElementById('lcdmh-nav');
  if (!container) return;

  fetch('nav.html?v=' + Date.now(), { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.text();
    })
    .then((html) => {
      container.innerHTML = html;
      initLCDMHNav();
    })
    .catch((error) => {
      console.error('Navigation non chargÃ©e :', error);
      container.innerHTML = '<div style="background:#e67e22;color:#fff;padding:1rem;text-align:center;font-family:Arial,sans-serif;">Menu temporairement indisponible â€” <a href="index.html" style="color:#fff;font-weight:bold;">Accueil</a></div>';
    });

  function initLCDMHNav() {
    const nav = document.getElementById('lcdmh-nav');
    if (!nav) return;

    const navLinks = nav.querySelector('#lcdmh-nav-links');
    const menuToggle = nav.querySelector('#lcdmh-menu-toggle');
    const pageRaw = (window.location.pathname.split('/').pop() || 'index.html').toLowerCase();
    const currentPage = pageRaw === '' || pageRaw === '/' ? 'index.html' : (pageRaw.startsWith('index') ? 'index.html' : pageRaw);
    let closeTimer = null;

    function clearCloseTimer() {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
    }

    function closeAllDropdowns() {
      nav.querySelectorAll('.lcdmh-has-drop.open').forEach((item) => item.classList.remove('open'));
      nav.querySelectorAll('.lcdmh-has-drop > a[aria-expanded="true"]').forEach((trigger) => trigger.setAttribute('aria-expanded', 'false'));
    }

    function openDropdown(item) {
      closeAllDropdowns();
      item.classList.add('open');
      const trigger = item.querySelector(':scope > a');
      if (trigger) trigger.setAttribute('aria-expanded', 'true');
    }

    nav.querySelectorAll('a[href]').forEach((link) => {
      const href = (link.getAttribute('href') || '').trim();
      if (!href || href === '#' || href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:')) return;

      const normalizedHref = href.split('?')[0].split('#')[0].toLowerCase() || 'index.html';
      const sameIndexAnchor = currentPage === 'index.html' && normalizedHref === 'index.html';
      if (normalizedHref === currentPage || sameIndexAnchor) {
        link.classList.add('active');
        const parentDropdown = link.closest('.lcdmh-has-drop');
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
        if (!isOpen) closeAllDropdowns();
      });
    }

    nav.querySelectorAll('.lcdmh-has-drop').forEach((item) => {
      const trigger = item.querySelector(':scope > a');
      if (!trigger) return;

      item.addEventListener('mouseenter', () => {
        if (window.innerWidth <= 1100) return;
        clearCloseTimer();
        openDropdown(item);
      });

      item.addEventListener('mouseleave', () => {
        if (window.innerWidth <= 1100) return;
        clearCloseTimer();
        closeTimer = setTimeout(() => {
          closeAllDropdowns();
        }, 420);
      });

      trigger.addEventListener('click', (event) => {
        const isMobile = window.innerWidth <= 1100;
        const href = (trigger.getAttribute('href') || '').trim();
        const usesToggleOnly = href === '#' || href === '';
        if (usesToggleOnly) event.preventDefault();

        if (isMobile) {
          const wasOpen = item.classList.contains('open');
          closeAllDropdowns();
          if (!wasOpen) openDropdown(item);
          return;
        }

        const wasOpen = item.classList.contains('open');
        if (usesToggleOnly) {
          if (wasOpen) {
            closeAllDropdowns();
          } else {
            openDropdown(item);
          }
        }
      });
    });

    nav.querySelectorAll('.lcdmh-dropdown a').forEach((link) => {
      link.addEventListener('click', () => {
        if (navLinks) navLinks.classList.remove('active');
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
        closeAllDropdowns();
      });
    });

    document.addEventListener('click', (event) => {
      if (!nav.contains(event.target)) {
        if (navLinks) navLinks.classList.remove('active');
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
        closeAllDropdowns();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        if (navLinks) navLinks.classList.remove('active');
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
        closeAllDropdowns();
      }
    });

    window.addEventListener('resize', () => {
      clearCloseTimer();
      if (window.innerWidth > 1100) {
        if (navLinks) navLinks.classList.remove('active');
        if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
      }
      closeAllDropdowns();
    });
  }
})();
