/**
 * page-content.js — LCDMH
 * Lit data/pages/{slug}.json et remplit automatiquement la page produit.
 * Le slug est détecté depuis le nom du fichier HTML (ex: komobi.html → komobi).
 *
 * Usage : ajouter dans le <head> de la page produit :
 *   <script src="js/page-content.js"></script>
 */
(function () {

  // ── Détecter le slug depuis l'URL ──────────────────────────────────────────
  const slug = location.pathname
    .split('/')
    .pop()
    .replace('.html', '') || 'index';

  const JSON_URL = `data/pages/${slug}.json`;

  // ── Utilitaires ────────────────────────────────────────────────────────────
  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function stars(rating) {
    const full  = Math.floor(rating);
    const half  = rating % 1 >= 0.5 ? 1 : 0;
    const empty = 5 - full - half;
    return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty);
  }

  function nl2br(s) {
    return String(s || '').replace(/\n/g, '<br>');
  }

  // ── SEO ────────────────────────────────────────────────────────────────────
  function applySEO(seo) {
    if (!seo) return;
    if (seo.title)       document.title = seo.title;
    setMeta('name',      'description', seo.description);
    setMeta('name',      'keywords',    seo.keywords);
    setMeta('property',  'og:title',    seo.title);
    setMeta('property',  'og:description', seo.description);
    setMeta('property',  'og:image',    seo.og_image);
    setLink('canonical', seo.canonical);
  }

  function setMeta(attr, name, content) {
    if (!content) return;
    let el = document.querySelector(`meta[${attr}="${name}"]`);
    if (!el) { el = document.createElement('meta'); el.setAttribute(attr, name); document.head.appendChild(el); }
    el.setAttribute('content', content);
  }

  function setLink(rel, href) {
    if (!href) return;
    let el = document.querySelector(`link[rel="${rel}"]`);
    if (!el) { el = document.createElement('link'); el.setAttribute('rel', rel); document.head.appendChild(el); }
    el.setAttribute('href', href);
  }

  // ── HERO ───────────────────────────────────────────────────────────────────
  function applyHero(hero) {
    if (!hero) return;

    // Badge
    const badge = document.querySelector('.hero-badge');
    if (badge && hero.badge) badge.textContent = hero.badge;

    // Titre
    const h1 = document.querySelector('.hero h1, .hero-content h1');
    if (h1 && hero.title) h1.textContent = hero.title;

    // Slogan principal
    const slogan = document.querySelector('.hero-slogan');
    if (slogan && hero.slogan) slogan.innerHTML = nl2br(hero.slogan);

    // Sous-slogan
    const subSlogan = document.querySelector('.hero-sub-slogan');
    if (subSlogan && hero.sub_slogan) subSlogan.innerHTML = nl2br(hero.sub_slogan);

    // Ligne de features
    const featLine = document.querySelector('.hero-content > p');
    if (featLine && hero.features_line) featLine.innerHTML = esc(hero.features_line);

    // Image de fond
    if (hero.background_image) {
      const heroEl = document.querySelector('.hero');
      if (heroEl) {
        heroEl.style.background = `linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)), url('${hero.background_image}') center/cover no-repeat scroll`;
      }
    }
  }

  // ── INTRO ──────────────────────────────────────────────────────────────────
  function applyIntro(intro) {
    if (!intro || !intro.text) return;
    const el = document.querySelector('.section-title > p');
    if (el) el.innerHTML = intro.text;
  }

  // ── FONCTIONS CLÉS ─────────────────────────────────────────────────────────
  function applyKeyFeatures(features) {
    if (!features || !features.length) return;
    const cards = document.querySelectorAll('.feature-card');
    features.forEach((feat, i) => {
      if (!cards[i]) return;
      const img = cards[i].querySelector('.feature-img');
      if (img && feat.image)     { img.src = feat.image; img.alt = feat.image_alt || ''; }
      const h3 = cards[i].querySelector('h3');
      if (h3 && feat.title)      h3.textContent = (feat.icon ? feat.icon + ' ' : '') + feat.title;
      const p  = cards[i].querySelector('p');
      if (p  && feat.text)       p.textContent = feat.text;
    });
  }

  // ── BLOC PRODUIT ───────────────────────────────────────────────────────────
  function applyProduct(product) {
    if (!product) return;

    // Image produit
    const img = document.querySelector('.product-showcase img');
    if (img) {
      if (product.image)     img.src = product.image;
      if (product.image_alt) img.alt = product.image_alt;
    }

    // Tagline
    const tagline = document.querySelector('.product-showcase h3');
    if (tagline && product.tagline) tagline.textContent = product.tagline;

    // Description
    const desc = document.querySelector('.product-showcase > div > p');
    if (desc && product.description) desc.textContent = product.description;

    // Code promo
    const promo = document.querySelector('.promo-code');
    if (promo && product.promo_code) {
      promo.textContent = `🔥 ÉCONOMISEZ ${product.promo_discount || ''} AVEC LE CODE : ${product.promo_code}`;
    }

    // Note / rating
    const rating = document.querySelector('.rating');
    if (rating && product.rating) {
      rating.textContent = `${stars(product.rating)} ${product.rating}/5 (${product.rating_count || 0} avis)`;
    }

    // Bouton principal
    const btnMain = document.querySelector('.btn-group .btn-orange');
    if (btnMain && product.affiliate_url) {
      btnMain.href = product.affiliate_url;
      if (product.promo_code && product.promo_discount) {
        btnMain.textContent = `🛒 Acheter ${product.promo_discount} avec code ${product.promo_code}`;
      }
    }

    // Note légale
    const note = document.querySelector('.product-showcase > div > p:last-child');
    if (note && product.note) note.textContent = product.note;
  }

  // ── STATUT DU TEST ─────────────────────────────────────────────────────────
  function applyTestStatus(test) {
    if (!test) return;
    const box = document.querySelector('.pending-box');
    if (!box) return;

    // Titre
    const h3 = box.querySelector('h3');
    if (h3 && test.label) h3.textContent = (test.status === 'done' ? '✅' : test.status === 'ongoing' ? '🔄' : '🔜') + ' ' + test.label;

    // Texte principal
    const paras = box.querySelectorAll('p');
    if (paras[0] && test.text)     paras[0].textContent = test.text;
    if (paras[1] && test.sub_text) { paras[1].style.fontStyle = 'italic'; paras[1].textContent = test.sub_text; }

    // Si test fait → afficher la note
    if (test.status === 'done' && test.rating) {
      const ratingEl = document.createElement('div');
      ratingEl.style.cssText = 'font-size:1.8rem;color:#e67e22;margin:1rem 0';
      ratingEl.textContent = `${stars(test.rating)} ${test.rating}/5`;
      if (test.rating_label) {
        const lbl = document.createElement('p');
        lbl.style.cssText = 'font-size:.9rem;color:#666;margin-top:.3rem';
        lbl.textContent = test.rating_label;
        ratingEl.appendChild(lbl);
      }
      h3.after(ratingEl);
    }

    // Bouton CTA
    const btn = box.querySelector('.btn');
    if (btn) {
      if (test.cta_url)   btn.href        = test.cta_url;
      if (test.cta_label) btn.textContent = test.cta_label;
    }
  }

  // ── POURQUOI CHOISIR ───────────────────────────────────────────────────────
  function applyWhyChoose(items) {
    if (!items || !items.length) return;
    const cards = document.querySelectorAll('.why-card');
    items.forEach((item, i) => {
      if (!cards[i]) return;
      const h3 = cards[i].querySelector('h3');
      if (h3 && item.title) h3.textContent = (item.icon ? item.icon + ' ' : '') + item.title;
      const p  = cards[i].querySelector('p');
      if (p  && item.text)  p.textContent = item.text;
    });
  }

  // ── SECTION VIDÉOS ─────────────────────────────────────────────────────────
  function applyVideos(videos) {
    if (!videos || !videos.enabled) return;

    // Créer le conteneur vidéos avant le footer s'il n'existe pas
    let feedContainer = document.getElementById('page-video-feed');
    if (!feedContainer) {
      feedContainer = document.createElement('div');
      feedContainer.className = 'container';
      feedContainer.innerHTML = '<div id="page-video-feed"></div>';
      const footer = document.querySelector('footer');
      if (footer) footer.before(feedContainer);
    }

    // Injecter product-feed.js dynamiquement
    const script = document.createElement('script');
    script.src = 'js/product-feed.js';
    script.setAttribute('data-keywords', videos.keywords || slug);
    script.setAttribute('data-max', String(videos.max || 4));
    script.setAttribute('data-container', 'page-video-feed');
    document.body.appendChild(script);
  }

  // ── ORCHESTRATEUR PRINCIPAL ────────────────────────────────────────────────
  function applyData(data) {
    applySEO(data.seo);
    applyHero(data.hero);
    applyIntro(data.intro);
    applyKeyFeatures(data.key_features);
    applyProduct(data.product);
    applyTestStatus(data.test_status);
    applyWhyChoose(data.why_choose);
    applyVideos(data.videos);
  }

  // ── CHARGEMENT ─────────────────────────────────────────────────────────────
  function init() {
    fetch(JSON_URL + '?t=' + Date.now())
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(applyData)
      .catch(err => {
        // Silencieux : si le JSON est absent, la page HTML statique s'affiche normalement
        console.warn('[page-content.js] JSON non trouvé pour "' + slug + '" :', err.message);
      });
  }

  // Attendre que le DOM soit prêt
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
