/**
 * LCDMH — Maillage Interne Automatique
 * =====================================
 * 1. Bloc "À lire aussi" (articles liés par thème) — injecté avant le footer
 * 2. Liens contextuels dans le texte (mots-clés → pages internes)
 * 
 * Usage : ajouter <script src="maillage.js"></script> avant </body>
 */

(function () {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  //  CONFIGURATION : relations entre pages
  // ═══════════════════════════════════════════════════════════════════════

  const PAGES = {
    'cap-nord-moto.html':        { title: 'Road Trip Cap Nord', cat: 'roadtrip', icon: '🏔️' },
    'les-alpes-dans-tous-les-sens.html': { title: 'Road Trip Alpes', cat: 'roadtrip', icon: '⛰️' },
    'alpes-aventure-festival-moto.html': { title: 'Alpes : Annecy → Nice', cat: 'roadtrip', icon: '🏍️' },
    'alpes-cols-mythiques.html':  { title: '47 Vidéos Alpes', cat: 'roadtrip', icon: '🎬' },
    'europe-asie-moto.html':     { title: 'Road Trip Istanbul & Cappadoce', cat: 'roadtrip', icon: '🌍' },
    'espagne-2023.html':         { title: 'Tour d\'Espagne à Moto', cat: 'roadtrip', icon: '🇪🇸' },
    'ecosse-irlande.html':       { title: 'Écosse & Irlande 2026', cat: 'roadtrip', icon: '🏴' },
    'roadtrips.html':            { title: 'Tous les Road Trips', cat: 'roadtrip', icon: '🗺️' },
    'pneus.html':                { title: 'Comparatif Pneus Moto', cat: 'test', icon: '🛞' },
    'aoocci.html':               { title: 'Test GPS Aoocci', cat: 'test', icon: '📍' },
    'carpuride.html':            { title: 'Test Carpuride CarPlay', cat: 'test', icon: '📱' },
    'gps.html':                  { title: 'Quel GPS Moto Choisir ?', cat: 'test', icon: '🧭' },
    'komobi.html':               { title: 'Traceur GPS Komobi', cat: 'test', icon: '🛡️' },
    'intercoms.html':            { title: 'Test Intercoms Moto', cat: 'test', icon: '🎧' },
    'olight.html':               { title: 'Test Olight Perun 3', cat: 'test', icon: '🔦' },
    'blackview.html':            { title: 'Test Blackview Xplore X1', cat: 'test', icon: '📱' },
    'aferiy.html':               { title: 'Test AFERIY Nano 100', cat: 'test', icon: '🔋' },
    'equipement.html':           { title: 'Équipement Road Trip', cat: 'test', icon: '🧥' },
    'photo-video.html':          { title: 'Matériel Vidéo Moto', cat: 'test', icon: '📷' },
    'tests-motos.html':          { title: 'Tests Motos', cat: 'test', icon: '🏍️' },
    'securite.html':             { title: 'Sécurité Moto', cat: 'conseil', icon: '🛡️' },
    'codes-promo.html':          { title: 'Codes Promo Moto', cat: 'promo', icon: '🎁' },
  };

  // Relations manuelles : pour chaque page, les pages les plus pertinentes
  const RELATIONS = {
    'cap-nord-moto.html':        ['roadtrips.html', 'pneus.html', 'equipement.html', 'aoocci.html', 'olight.html', 'aferiy.html'],
    'les-alpes-dans-tous-les-sens.html': ['alpes-cols-mythiques.html', 'roadtrips.html', 'pneus.html', 'alpes-aventure-festival-moto.html'],
    'alpes-aventure-festival-moto.html': ['les-alpes-dans-tous-les-sens.html', 'alpes-cols-mythiques.html', 'roadtrips.html', 'equipement.html'],
    'alpes-cols-mythiques.html':  ['les-alpes-dans-tous-les-sens.html', 'alpes-aventure-festival-moto.html', 'roadtrips.html'],
    'europe-asie-moto.html':     ['roadtrips.html', 'pneus.html', 'equipement.html', 'cap-nord-moto.html', 'espagne-2023.html'],
    'espagne-2023.html':         ['roadtrips.html', 'europe-asie-moto.html', 'pneus.html', 'equipement.html'],
    'ecosse-irlande.html':       ['roadtrips.html', 'cap-nord-moto.html', 'equipement.html', 'olight.html', 'aferiy.html'],
    'roadtrips.html':            ['cap-nord-moto.html', 'europe-asie-moto.html', 'espagne-2023.html', 'les-alpes-dans-tous-les-sens.html', 'ecosse-irlande.html'],
    'pneus.html':                ['roadtrips.html', 'gps.html', 'equipement.html', 'codes-promo.html'],
    'aoocci.html':               ['carpuride.html', 'gps.html', 'codes-promo.html', 'roadtrips.html'],
    'carpuride.html':            ['aoocci.html', 'gps.html', 'codes-promo.html', 'roadtrips.html'],
    'gps.html':                  ['aoocci.html', 'carpuride.html', 'codes-promo.html', 'roadtrips.html'],
    'komobi.html':               ['securite.html', 'equipement.html', 'codes-promo.html', 'roadtrips.html'],
    'intercoms.html':            ['equipement.html', 'gps.html', 'codes-promo.html'],
    'olight.html':               ['aferiy.html', 'equipement.html', 'cap-nord-moto.html', 'codes-promo.html'],
    'blackview.html':            ['equipement.html', 'photo-video.html', 'codes-promo.html'],
    'aferiy.html':               ['olight.html', 'equipement.html', 'cap-nord-moto.html', 'codes-promo.html'],
    'equipement.html':           ['pneus.html', 'gps.html', 'intercoms.html', 'olight.html', 'roadtrips.html'],
    'photo-video.html':          ['equipement.html', 'roadtrips.html', 'blackview.html'],
    'tests-motos.html':          ['pneus.html', 'equipement.html', 'roadtrips.html'],
    'securite.html':             ['komobi.html', 'equipement.html', 'roadtrips.html'],
    'codes-promo.html':          ['aoocci.html', 'carpuride.html', 'pneus.html', 'olight.html', 'aferiy.html', 'komobi.html'],
    'index.html':                ['roadtrips.html', 'cap-nord-moto.html', 'pneus.html', 'codes-promo.html', 'gps.html'],
    'a-propos.html':             ['roadtrips.html', 'contact.html', 'codes-promo.html'],
    'contact.html':              ['a-propos.html', 'roadtrips.html', 'codes-promo.html'],
  };

  // ═══════════════════════════════════════════════════════════════════════
  //  MOTS-CLÉS CONTEXTUELS (maillage dans le texte)
  // ═══════════════════════════════════════════════════════════════════════

  const KEYWORD_LINKS = [
    { keywords: ['aoocci', 'gps aoocci'],       url: 'aoocci.html',       label: 'Test GPS Aoocci' },
    { keywords: ['carpuride', 'carplay moto'],   url: 'carpuride.html',    label: 'Test Carpuride' },
    { keywords: ['komobi', 'traceur gps', 'antivol moto'], url: 'komobi.html', label: 'Traceur Komobi' },
    { keywords: ['olight', 'perun 3', 'lampe frontale'],   url: 'olight.html',  label: 'Test Olight' },
    { keywords: ['aferiy', 'batterie portable', 'station énergie'], url: 'aferiy.html', label: 'Test AFERIY' },
    { keywords: ['blackview', 'xplore x1'],      url: 'blackview.html',    label: 'Test Blackview' },
    { keywords: ['dunlop mutant', 'bridgestone t33', 'michelin road 6'], url: 'pneus.html', label: 'Comparatif pneus' },
    { keywords: ['cap nord'],                     url: 'cap-nord-moto.html', label: 'Road Trip Cap Nord' },
    { keywords: ['cappadoce', 'istanbul', 'balkans'], url: 'europe-asie-moto.html', label: 'Road Trip Europe-Asie' },
    { keywords: ['écosse', 'irlande', 'highlands', 'nc500'], url: 'ecosse-irlande.html', label: 'Road Trip Écosse' },
    { keywords: ['codes promo', 'code promo', 'réduction'], url: 'codes-promo.html', label: 'Codes promo' },
    { keywords: ['intercom', 'sena', 'cardo'],   url: 'intercoms.html',    label: 'Test intercoms' },
  ];

  // ═══════════════════════════════════════════════════════════════════════
  //  1. BLOC "À LIRE AUSSI"
  // ═══════════════════════════════════════════════════════════════════════

  function getCurrentPage() {
    const path = window.location.pathname;
    const filename = path.split('/').pop() || 'index.html';
    return filename;
  }

  function getRelatedPages(currentPage) {
    // D'abord les relations manuelles
    let related = RELATIONS[currentPage] || [];

    // Si pas assez, compléter avec des pages de la même catégorie
    if (related.length < 4) {
      const currentCat = PAGES[currentPage]?.cat;
      if (currentCat) {
        const sameCat = Object.entries(PAGES)
          .filter(([page, info]) => info.cat === currentCat && page !== currentPage && !related.includes(page))
          .map(([page]) => page);
        related = related.concat(sameCat);
      }
    }

    // Toujours ajouter roadtrips et codes-promo si pas déjà là
    if (!related.includes('roadtrips.html') && currentPage !== 'roadtrips.html') {
      related.push('roadtrips.html');
    }
    if (!related.includes('codes-promo.html') && currentPage !== 'codes-promo.html') {
      related.push('codes-promo.html');
    }

    // Max 6 liens
    return related.slice(0, 6).filter(page => page !== currentPage && PAGES[page]);
  }

  function injectRelatedBlock() {
    const currentPage = getCurrentPage();
    const related = getRelatedPages(currentPage);

    if (related.length === 0) return;

    // Construire le HTML
    const linksHtml = related.map(page => {
      const info = PAGES[page];
      return `<a href="${page}" class="maillage-link">${info.icon} ${info.title}</a>`;
    }).join('\n');

    const blockHtml = `
    <section class="maillage-section" aria-label="Articles liés">
      <div class="maillage-inner">
        <h3 class="maillage-title">📖 À lire aussi</h3>
        <div class="maillage-grid">
          ${linksHtml}
        </div>
      </div>
    </section>`;

    // Injecter avant le footer
    const footer = document.querySelector('footer');
    if (footer) {
      footer.insertAdjacentHTML('beforebegin', blockHtml);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  2. LIENS CONTEXTUELS DANS LE TEXTE
  // ═══════════════════════════════════════════════════════════════════════

  function injectContextualLinks() {
    const currentPage = getCurrentPage();

    // Ne pas injecter de liens vers la page courante
    const relevantKeywords = KEYWORD_LINKS.filter(kl => {
      const targetFile = kl.url.split('/').pop();
      return targetFile !== currentPage;
    });

    if (relevantKeywords.length === 0) return;

    // Sélectionner le contenu principal (pas nav, pas footer)
    const mainContent = document.querySelector('main, .content, article, [role="main"]');
    if (!mainContent) return;

    // Parcourir les paragraphes
    const paragraphs = mainContent.querySelectorAll('p');
    const alreadyLinked = new Set(); // Un seul lien par mot-clé par page

    paragraphs.forEach(p => {
      // Ne pas toucher les paragraphes qui ont déjà des liens internes
      if (p.querySelector('a[href*=".html"]')) return;

      let html = p.innerHTML;
      let modified = false;

      for (const kl of relevantKeywords) {
        if (alreadyLinked.has(kl.url)) continue;

        for (const keyword of kl.keywords) {
          // Regex insensible à la casse, mot entier
          const regex = new RegExp(`\\b(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\b`, 'i');
          if (regex.test(html)) {
            html = html.replace(regex, `<a href="${kl.url}" class="maillage-contextual" title="${kl.label}">$1</a>`);
            alreadyLinked.add(kl.url);
            modified = true;
            break; // Un seul match par keyword group
          }
        }
      }

      if (modified) {
        p.innerHTML = html;
      }
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  STYLES
  // ═══════════════════════════════════════════════════════════════════════

  function injectStyles() {
    const css = `
    .maillage-section {
      background: linear-gradient(135deg, #f7f7f5 0%, #f0ede8 100%);
      padding: 2.5rem 1rem;
      margin: 0;
    }
    .maillage-inner {
      max-width: 1100px;
      margin: 0 auto;
    }
    .maillage-title {
      font-family: 'Montserrat', sans-serif;
      font-size: 1.25rem;
      color: #1a1a1a;
      margin: 0 0 1.2rem;
      text-align: center;
    }
    .maillage-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 0.75rem;
    }
    .maillage-link {
      display: block;
      padding: 0.9rem 1.1rem;
      background: #fff;
      border-radius: 10px;
      color: #1a1a1a;
      font-weight: 600;
      font-size: 0.92rem;
      text-decoration: none;
      border: 1px solid #e5e5e5;
      transition: all 0.2s ease;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .maillage-link:hover {
      border-color: #e67e22;
      color: #e67e22;
      box-shadow: 0 3px 12px rgba(230, 126, 34, 0.12);
      transform: translateY(-1px);
    }
    .maillage-contextual {
      color: #e67e22;
      text-decoration: none;
      border-bottom: 1px dotted #e67e22;
      font-weight: inherit;
    }
    .maillage-contextual:hover {
      color: #d35400;
      border-bottom-style: solid;
    }
    @media (max-width: 640px) {
      .maillage-grid {
        grid-template-columns: 1fr;
      }
      .maillage-section {
        padding: 1.5rem 1rem;
      }
    }
    `;

    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  INIT
  // ═══════════════════════════════════════════════════════════════════════

  function init() {
    const currentPage = getCurrentPage();
    // Ne pas injecter sur sitemap, contact, nav
    const skipPages = ['sitemap.html', 'nav.html', 'widget-roadtrip-snippet.html'];
    if (skipPages.includes(currentPage)) return;

    injectStyles();
    injectRelatedBlock();
    injectContextualLinks();
  }

  // Attendre que le DOM soit prêt
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
