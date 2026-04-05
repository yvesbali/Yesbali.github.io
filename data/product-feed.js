/**
 * product-feed.js — LCDMH
 * Affiche les vidéos YouTube liées à une page produit.
 * Lit data/videos.json et filtre par mots-clés dans le TITRE uniquement.
 * 
 * Structure videos.json attendue :
 *   { videos: [{title, url, thumb, published, ...}], shorts: [{title, short_url, thumb, ...}] }
 * 
 * Usage :
 *   <script src="js/product-feed.js"
 *           data-keywords="komobi"
 *           data-max="4"
 *           data-container="komobi-video-feed">
 *   </script>
 */
(function () {
  const script   = document.currentScript;
  const keywords = (script.getAttribute('data-keywords') || '').toLowerCase().split(',').map(k => k.trim()).filter(Boolean);
  const maxItems = parseInt(script.getAttribute('data-max') || '4', 10);
  const containerId = script.getAttribute('data-container') || 'product-video-feed';

  const VIDEOS_JSON = 'data/videos.json';

  /* ── Styles (injectés une seule fois) ─────────────────────────────────────── */
  if (!document.getElementById('pf-style')) {
    const style = document.createElement('style');
    style.id = 'pf-style';
    style.textContent = `
      .pf-section { margin: 3rem 0; }
      .pf-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 2rem; font-weight: 800;
        text-align: center; margin-bottom: 0.4rem; color: #1a1a1a;
      }
      .pf-title em { font-style: normal; color: #e67e22; }
      .pf-bar { width: 52px; height: 4px; background: #e67e22; border-radius: 2px; margin: 0.6rem auto 2.2rem; }
      .pf-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1.5rem;
      }
      .pf-card {
        background: #fff; border: 1px solid #e5e5e5; border-radius: 14px;
        overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,.06);
        transition: transform .2s, box-shadow .2s;
        text-decoration: none; color: inherit;
        display: flex; flex-direction: column;
      }
      .pf-card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,.12); }
      .pf-thumb-wrap {
        position: relative; padding-top: 56.25%;
        background: #222; overflow: hidden;
      }
      .pf-thumb-wrap img {
        position: absolute; inset: 0;
        width: 100%; height: 100%; object-fit: cover;
        transition: transform .3s;
      }
      .pf-card:hover .pf-thumb-wrap img { transform: scale(1.04); }
      .pf-play {
        position: absolute; inset: 0;
        display: flex; align-items: center; justify-content: center;
        background: rgba(0,0,0,.25); transition: background .2s;
      }
      .pf-card:hover .pf-play { background: rgba(0,0,0,.42); }
      .pf-play-btn {
        width: 54px; height: 54px; background: #e67e22; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.4rem; box-shadow: 0 4px 14px rgba(0,0,0,.35);
        color: #fff; line-height: 1;
      }
      .pf-badge {
        position: absolute; top: 10px; left: 10px;
        font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: .06em; padding: 3px 9px; border-radius: 20px;
        color: #fff;
      }
      .pf-badge-video { background: #e67e22; }
      .pf-badge-short { background: #ff0000; }
      .pf-body {
        padding: 1rem 1.1rem 1.2rem;
        flex: 1; display: flex; flex-direction: column; gap: 0.3rem;
      }
      .pf-card-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 1rem; font-weight: 700; line-height: 1.35; color: #1a1a1a;
        display: -webkit-box; -webkit-line-clamp: 2;
        -webkit-box-orient: vertical; overflow: hidden;
      }
      .pf-date { font-size: 0.8rem; color: #999; margin-top: auto; padding-top: 0.4rem; }
      .pf-more {
        display: inline-flex; align-items: center; gap: 6px;
        margin-top: 1.8rem; font-family: 'Montserrat', sans-serif;
        font-size: 0.9rem; font-weight: 700; color: #e67e22;
        text-decoration: none; transition: color .2s;
      }
      .pf-more:hover { color: #d35400; }
      @media (max-width: 600px) { .pf-grid { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
  }

  /* ── Conteneur ─────────────────────────────────────────────────────────────── */
  function getContainer() {
    let el = document.getElementById(containerId);
    if (!el) {
      el = document.createElement('div');
      el.id = containerId;
      script.parentNode.insertBefore(el, script.nextSibling);
    }
    return el;
  }

  /* ── Filtrage : le mot-clé principal doit être dans le TITRE ──────────────── */
  function matches(title) {
    if (!keywords.length) return true;
    const t = (title || '').toLowerCase();
    return keywords.some(k => t.includes(k));
  }

  /* ── Extraire l'ID YouTube depuis une URL ─────────────────────────────────── */
  function extractId(url) {
    if (!url) return '';
    // https://www.youtube.com/watch?v=XXXX  ou  https://youtube.com/shorts/XXXX
    const m = url.match(/(?:v=|shorts\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : '';
  }

  /* ── Formater la date ─────────────────────────────────────────────────────── */
  function fmtDate(str) {
    if (!str) return '';
    const d = new Date(str);
    return isNaN(d) ? '' : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  /* ── Construire une carte ─────────────────────────────────────────────────── */
  function buildCard(item, isShort) {
    const rawUrl = item.url || item.short_url || '';
    const id    = extractId(rawUrl);
    // Construire une URL propre pour éviter les problèmes d'encodage avec certains IDs
    let url = rawUrl;
    if (id && !url) {
      url = isShort ? `https://youtube.com/shorts/${id}` : `https://www.youtube.com/watch?v=${id}`;
    }
    const thumb = item.thumb || (id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : '');
    const date  = fmtDate(item.published);
    const safeUrl = url.replace(/"/g, '&quot;');
    const safeTitle = (item.title || '').replace(/"/g, '&quot;');

    return `
      <a class="pf-card" href="${safeUrl}" target="_blank" rel="noopener noreferrer">
        <div class="pf-thumb-wrap">
          <img src="${thumb}"
               alt="${safeTitle}"
               loading="lazy"
               onerror="this.onerror=null;this.src='https://i.ytimg.com/vi/${id}/mqdefault.jpg'">
          <div class="pf-play"><div class="pf-play-btn">&#9654;</div></div>
          <span class="pf-badge ${isShort ? 'pf-badge-short' : 'pf-badge-video'}">${isShort ? 'Short' : 'Vidéo'}</span>
        </div>
        <div class="pf-body">
          <div class="pf-card-title">${item.title || 'Vidéo LCDMH'}</div>
          ${date ? `<div class="pf-date">📅 ${date}</div>` : ''}
        </div>
      </a>`;
  }

  /* ── Rendu ────────────────────────────────────────────────────────────────── */
  function render(data) {
    const container = getContainer();

    // Collecter vidéos + shorts correspondant aux mots-clés
    const videos = (data.videos || []).filter(v => matches(v.title));
    const shorts = (data.shorts || []).filter(s => matches(s.title));

    // Vidéos longues en premier, puis shorts, limité à maxItems
    const results = [
      ...videos.map(v => ({ item: v, isShort: false })),
      ...shorts.map(s => ({ item: s, isShort: true }))
    ].slice(0, maxItems);

    if (!results.length) { container.innerHTML = ''; return; }

    // Titre dynamique : utilise le premier mot-clé, capitalisé
    const prodName = (keywords[0] || 'LCDMH').toUpperCase();

    container.innerHTML = `
      <div class="pf-section">
        <div class="pf-title">Mes vidéos sur <em>${prodName}</em></div>
        <div class="pf-bar"></div>
        <div class="pf-grid">
          ${results.map(r => buildCard(r.item, r.isShort)).join('')}
        </div>
        <div style="text-align:center">
          <a class="pf-more" href="https://www.youtube.com/@LCDMH" target="_blank" rel="noopener">
            &#9654; Voir toutes mes vidéos sur YouTube
          </a>
        </div>
      </div>`;
  }

  /* ── Chargement ───────────────────────────────────────────────────────────── */
  function init() {
    const container = getContainer();

    // Timeout de sécurité : si rien ne s'affiche après 6s, on vide silencieusement
    const timeout = setTimeout(() => { container.innerHTML = ''; }, 6000);

    fetch(VIDEOS_JSON + '?t=' + Date.now())
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(data => { clearTimeout(timeout); render(data); })
      .catch(() => { clearTimeout(timeout); container.innerHTML = ''; });
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();

})();
