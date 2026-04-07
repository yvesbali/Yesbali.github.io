/**
 * page-content.js — LCDMH v2
 * Lit data/pages/{slug}.json et remplit la page produit.
 * Sélecteurs robustes, exécution garantie après DOM ready.
 */
(function () {
  // Gère /aferiy.html ET /aferiy/ (Hugo)
  let slug = location.pathname.replace(/\/$/, '').split('/').pop().replace('.html', '') || 'index';
  if (slug === '' || slug === 'index') {
    const parts = location.pathname.replace(/\/$/, '').split('/').filter(p => p);
    slug = parts[parts.length - 1] || 'index';
  }
  const JSON_URL = '/data/pages/' + slug + '.json';

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function nl2br(s) { return String(s || '').replace(/\n/g, '<br>'); }
  function stars(r) {
    r = parseFloat(r) || 0;
    const f = Math.floor(r), h = r % 1 >= 0.5 ? 1 : 0;
    return '★'.repeat(f) + (h ? '½' : '') + '☆'.repeat(5 - f - h);
  }

  // ── SEO ──────────────────────────────────────────────────
  function applySEO(seo) {
    if (!seo) return;
    if (seo.title) document.title = seo.title;
    [['name','description',seo.description],['name','keywords',seo.keywords],
     ['property','og:title',seo.title],['property','og:description',seo.description],
     ['property','og:image',seo.og_image]].forEach(([a,n,v]) => {
      if (!v) return;
      let el = document.querySelector('meta['+a+'="'+n+'"]');
      if (!el) { el = document.createElement('meta'); el.setAttribute(a,n); document.head.appendChild(el); }
      el.setAttribute('content', v);
    });
  }

  // ── HERO ─────────────────────────────────────────────────
  function applyHero(hero) {
    if (!hero) return;
    const set = (sel, val, html) => {
      const el = $(sel);
      if (el && val) { if (html) el.innerHTML = val; else el.textContent = val; }
    };
    set('.hero-badge', hero.badge);
    set('.hero h1', hero.title);
    set('.hero-slogan', nl2br(hero.slogan), true);
    set('.hero-sub-slogan', nl2br(hero.sub_slogan), true);
    // Ligne features : dernier <p> dans .hero-content
    const heroPs = $$('.hero-content > p');
    if (heroPs.length && hero.features_line) heroPs[heroPs.length - 1].innerHTML = hero.features_line;
    if (hero.background_image) {
      const heroEl = $('.hero');
      if (heroEl) heroEl.style.background = 'linear-gradient(rgba(0,0,0,0.5),rgba(0,0,0,0.5)),url("'+hero.background_image+'") center/cover no-repeat scroll';
    }
  }

  // ── INTRO ────────────────────────────────────────────────
  function applyIntro(intro) {
    if (!intro || !intro.text) return;
    // Le <p> d'intro est le premier <p> dans .section-title
    const candidates = $$('.section-title p');
    if (candidates.length) candidates[0].innerHTML = intro.text;
  }

  // ── 3 FONCTIONS CLÉS ─────────────────────────────────────
  function applyKeyFeatures(features) {
    if (!features || !features.length) return;
    $$('.feature-card').forEach((card, i) => {
      const feat = features[i];
      if (!feat) return;
      const img = card.querySelector('img');
      if (img) {
        if (feat.image) { img.src = feat.image; img.setAttribute('src', feat.image); }
        if (feat.image_alt) img.alt = feat.image_alt;
      }
      const h3 = card.querySelector('h3');
      if (h3 && feat.title) h3.textContent = (feat.icon ? feat.icon + ' ' : '') + feat.title;
      const p = card.querySelector('p');
      if (p && feat.text) p.textContent = feat.text;
    });
  }

  // ── BLOC PRODUIT ─────────────────────────────────────────
  function applyProduct(product) {
    if (!product) return;
    const showcase = $('.product-showcase');
    if (!showcase) return;

    const img = showcase.querySelector('img');
    if (img && product.image) { img.src = product.image; if (product.image_alt) img.alt = product.image_alt; }

    const h3 = showcase.querySelector('h3');
    if (h3 && product.tagline) h3.textContent = product.tagline;

    // Description : premier <p> dans la div de droite
    const divs = $$('.product-showcase > div');
    const rightDiv = divs.length > 1 ? divs[divs.length - 1] : showcase;
    const descP = rightDiv.querySelector('p');
    if (descP && product.description) descP.textContent = product.description;

    const promo = $('.promo-code');
    if (promo && product.promo_code) {
      promo.textContent = '🔥 ÉCONOMISEZ ' + (product.promo_discount || '') + ' AVEC LE CODE : ' + product.promo_code;
    }

    const rating = $('.rating');
    if (rating && product.rating) {
      rating.textContent = stars(product.rating) + ' ' + product.rating + '/5 (' + (product.rating_count || 0) + ' avis)';
    }

    const btnMain = showcase.querySelector('.btn-orange');
    if (btnMain && product.affiliate_url) {
      btnMain.href = product.affiliate_url;
      if (product.cta_label) btnMain.textContent = product.cta_label;
      else if (product.promo_code) btnMain.textContent = '🛒 Acheter ' + (product.promo_discount || '') + ' avec code ' + product.promo_code;
      else btnMain.textContent = '🛒 Voir les offres';
    }

    // Note légale : dernier <p> dans rightDiv
    const allPs = $$('p', rightDiv);
    const noteP = allPs[allPs.length - 1];
    if (noteP && product.note && noteP !== descP) noteP.textContent = product.note;
  }

  // ── STATUT DU TEST ───────────────────────────────────────
  function applyTestStatus(test) {
    if (!test) return;
    const box = $('.pending-box');
    if (!box) return;

    const icons = { done: '✅', ongoing: '🔄', pending: '🔜' };
    const h3 = box.querySelector('h3');
    if (h3 && test.label) h3.textContent = (icons[test.status] || '🔜') + ' ' + test.label;

    const paras = $$('p', box);
    if (paras[0] && test.text) paras[0].textContent = test.text;
    if (paras[1] && test.sub_text) paras[1].textContent = test.sub_text;

    if (test.status === 'done' && test.rating) {
      const rEl = document.createElement('div');
      rEl.style.cssText = 'font-size:1.8rem;color:#e67e22;margin:1rem 0;text-align:center';
      rEl.textContent = stars(test.rating) + ' ' + test.rating + '/5';
      if (test.rating_label) {
        const lbl = document.createElement('p');
        lbl.style.cssText = 'font-size:.9rem;color:#666;margin-top:.3rem';
        lbl.textContent = test.rating_label;
        rEl.appendChild(lbl);
      }
      if (h3) h3.after(rEl);
    }

    const btn = box.querySelector('a.btn, a.btn-orange');
    if (btn) {
      if (test.cta_url) btn.href = test.cta_url;
      if (test.cta_label) btn.textContent = test.cta_label;
    }
  }

  // ── POURQUOI CHOISIR ─────────────────────────────────────
  function applyWhyChoose(items) {
    if (!items || !items.length) return;
    $$('.why-card').forEach((card, i) => {
      const item = items[i];
      if (!item) return;
      const h3 = card.querySelector('h3');
      if (h3 && item.title) h3.textContent = (item.icon ? item.icon + ' ' : '') + item.title;
      const p = card.querySelector('p');
      if (p && item.text) p.textContent = item.text;
    });
  }

  // ── VIDÉOS ───────────────────────────────────────────────
  function applyVideos(videos) {
    if (!videos || !videos.enabled) return;
    // Ne pas dupliquer si product-feed est déjà dans le HTML (data-container présent)
    if (document.querySelector('[data-container]') || document.querySelector('script[src*="product-feed"]')) return;
    const wrap = document.createElement('div');
    wrap.className = 'container';
    wrap.innerHTML = '<div id="page-video-feed"></div>';
    const footer = $('footer');
    if (footer) footer.before(wrap);
    const script = document.createElement('script');
    script.src = 'js/product-feed.js';
    script.setAttribute('data-keywords', videos.keywords || slug);
    script.setAttribute('data-max', String(videos.max || 4));
    script.setAttribute('data-container', 'page-video-feed');
    document.body.appendChild(script);
  }

  // ── ORCHESTRATEUR ─────────────────────────────────────────
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

  // ── CHARGEMENT — garanti après DOM ready ─────────────────
  function init() {
    fetch(JSON_URL + '?t=' + Date.now())
      .then(function(r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(applyData)
      .catch(function(e) { console.warn('[page-content.js] ' + slug + ' : ' + e.message); });
  }

  // S'assurer que le DOM est complètement chargé avant d'agir
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // DOM déjà prêt mais on attend le prochain tick pour être sûr
    setTimeout(init, 0);
  }

})();
