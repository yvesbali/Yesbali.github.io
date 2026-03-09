(function () {
  'use strict';

  const WIDGET_ID = 'lcdmh-ressources';
  const STYLES_ID = 'lcdmh-roadbooks-widget-styles';
  const CACHE_BUST = Date.now();
  const DATA_SOURCES = [
    '/roadbooks.json?t=' + CACHE_BUST,
    'https://lcdmh.com/roadbooks.json?t=' + CACHE_BUST,
    'https://yvesbali.github.io/roadbooks.json?t=' + CACHE_BUST
  ];

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function injectStyles() {
    if (document.getElementById(STYLES_ID)) return;

    const style = document.createElement('style');
    style.id = STYLES_ID;
    style.textContent = `
      .lcdmh-rb-wrap{margin:22px auto 26px;max-width:1200px;padding:0 5%;}
      .lcdmh-rb-box{display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between;background:#fff8f0;border:2px solid #e67e22;border-radius:18px;padding:22px 24px;box-shadow:0 10px 28px rgba(0,0,0,.06)}
      .lcdmh-rb-main{flex:1 1 460px;min-width:280px}
      .lcdmh-rb-kicker{font:800 .8rem/1.2 Inter,Arial,sans-serif;color:#e67e22;letter-spacing:.02em;margin-bottom:8px;text-transform:uppercase}
      .lcdmh-rb-title{font:800 1.12rem/1.25 Montserrat,Arial,sans-serif;color:#1a1a1a;margin-bottom:14px}
      .lcdmh-rb-text{font:500 .92rem/1.55 Inter,Arial,sans-serif;color:#5f5f5f;margin-bottom:14px}
      .lcdmh-rb-actions{display:flex;flex-wrap:wrap;gap:12px}
      .lcdmh-rb-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 18px;border-radius:999px;font:700 .92rem/1 Inter,Arial,sans-serif;text-decoration:none;transition:transform .15s ease,opacity .15s ease,box-shadow .15s ease;white-space:nowrap;box-shadow:0 3px 10px rgba(0,0,0,.08)}
      .lcdmh-rb-btn:hover{opacity:.96;transform:translateY(-1px)}
      .lcdmh-rb-btn--trace{background:#e67e22;color:#fff}
      .lcdmh-rb-btn--pdf{background:#24384d;color:#fff}
      .lcdmh-rb-qr{flex:0 0 168px;min-width:140px;text-align:center}
      .lcdmh-rb-qrbox{background:#fff;border:2px dashed #e67e22;border-radius:14px;padding:12px}
      .lcdmh-rb-qrlabel{font:800 .72rem/1.2 Inter,Arial,sans-serif;color:#24384d;margin-bottom:6px}
      .lcdmh-rb-qr img{width:110px;height:110px;object-fit:contain;margin:0 auto 6px;display:block;border-radius:8px;background:#fff}
      .lcdmh-rb-qrsmall{font:600 .68rem/1.2 Inter,Arial,sans-serif;color:#777}
      .lcdmh-rb-note{font:600 .74rem/1.35 Inter,Arial,sans-serif;color:#8a8a8a;margin-top:12px}
      @media (max-width:720px){
        .lcdmh-rb-wrap{padding:0 4%}
        .lcdmh-rb-box{padding:18px}
        .lcdmh-rb-actions{flex-direction:column}
        .lcdmh-rb-btn{width:100%}
        .lcdmh-rb-qr{flex-basis:100%}
      }
    `;
    document.head.appendChild(style);
  }

  function getCurrentPageName() {
    let page = window.location.pathname.split('/').pop() || 'index.html';
    if (!page || page === '/') page = 'index.html';
    return page.toLowerCase();
  }

  function normalizePage(page) {
    return String(page || '').trim().toLowerCase();
  }

  function createButton(href, cls, icon, label) {
    const a = document.createElement('a');
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = 'lcdmh-rb-btn ' + cls;
    a.innerHTML = '<span>' + icon + '</span><span>' + escapeHtml(label) + '</span>';
    return a;
  }

  function ensureContainer() {
    return document.getElementById(WIDGET_ID);
  }

  function renderTrip(container, trip) {
    const wrap = document.createElement('section');
    wrap.className = 'lcdmh-rb-wrap';

    const box = document.createElement('div');
    box.className = 'lcdmh-rb-box';

    const introText =
      trip.description ||
      'Télécharge la trace Kurviger, le roadbook PDF et scanne le QR code pour récupérer rapidement les ressources de ce road trip.';

    const traceLabel =
      trip.trace_label ||
      'Télécharger la trace Kurviger';

    const noteText =
      trip.note ||
      'Note : la trace Kurviger et le roadbook PDF correspondent à la base du road trip réellement effectué. Selon la météo, l’état des routes, les imprévus, la fatigue ou la condition physique, l’itinéraire réel peut avoir légèrement varié.';

    const main = document.createElement('div');
    main.className = 'lcdmh-rb-main';
    main.innerHTML =
      '<div class="lcdmh-rb-kicker">📥 Ressources du voyage</div>' +
      '<div class="lcdmh-rb-title">' + escapeHtml(trip.titre || '') + '</div>' +
      '<div class="lcdmh-rb-text">' + escapeHtml(introText) + '</div>';

    const actions = document.createElement('div');
    actions.className = 'lcdmh-rb-actions';

    if (trip.gpx) {
      actions.appendChild(
        createButton(trip.gpx, 'lcdmh-rb-btn--trace', '🗺️', traceLabel)
      );
    }

    if (trip.roadbook) {
      actions.appendChild(
        createButton(
          trip.roadbook,
          'lcdmh-rb-btn--pdf',
          '📖',
          trip.roadbook_nom || 'Télécharger le roadbook PDF'
        )
      );
    }

    if (!actions.children.length) return;

    main.appendChild(actions);

    if (noteText) {
      main.insertAdjacentHTML(
        'beforeend',
        '<div class="lcdmh-rb-note">' + escapeHtml(noteText) + '</div>'
      );
    }

    box.appendChild(main);

    if (trip.qr_code) {
      const qr = document.createElement('div');
      qr.className = 'lcdmh-rb-qr';
      qr.innerHTML =
        '<div class="lcdmh-rb-qrbox">' +
        '<div class="lcdmh-rb-qrlabel">📱 SCANNE-MOI</div>' +
        '<img src="' + escapeHtml(trip.qr_code) + '" alt="QR code ressources voyage">' +
        '<div class="lcdmh-rb-qrsmall">Téléchargement direct</div>' +
        '</div>';
      box.appendChild(qr);
    }

    wrap.appendChild(box);
    container.replaceChildren(wrap);
  }

  async function loadRoadbooksData() {
    let lastError = null;

    for (const url of DATA_SOURCES) {
      try {
        const response = await fetch(url, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error('HTTP ' + response.status + ' sur ' + url);
        }
        return await response.json();
      } catch (err) {
        lastError = err;
      }
    }

    throw lastError || new Error('Impossible de charger roadbooks.json');
  }

  async function init() {
    const container = ensureContainer();
    if (!container) return;

    injectStyles();

    try {
      const data = await loadRoadbooksData();
      const current = getCurrentPageName();
      const trips = Array.isArray(data.trips) ? data.trips : [];

      const trip = trips.find(function (item) {
        return item && item.actif !== false && normalizePage(item.page) === current;
      });

      if (!trip) return;
      renderTrip(container, trip);
    } catch (err) {
      console.warn('LCDMH roadbooks widget non chargé :', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();