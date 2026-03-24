/**
 * product-feed.js — LCDMH
 * Affiche les vidéos YouTube liées à une page produit.
 * Lit data/videos.json et filtre par mots-clés.
 * Usage : <script src="js/product-feed.js" data-keywords="komobi,traceur,gps" data-max="4"></script>
 */
(function () {
  const script = document.currentScript;
  const keywords = (script.getAttribute('data-keywords') || '').toLowerCase().split(',').map(k => k.trim()).filter(Boolean);
  const maxVideos = parseInt(script.getAttribute('data-max') || '4', 10);
  const containerId = script.getAttribute('data-container') || 'product-video-feed';

  const VIDEOS_JSON = 'data/videos.json';

  // ── Styles injectés une seule fois ──────────────────────────────────────────
  if (!document.getElementById('pf-style')) {
    const style = document.createElement('style');
    style.id = 'pf-style';
    style.textContent = `
      .pf-section {
        margin: 3rem 0;
      }
      .pf-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0.4rem;
        color: #1a1a1a;
      }
      .pf-title em { font-style: normal; color: #e67e22; }
      .pf-bar {
        width: 52px; height: 4px;
        background: #e67e22; border-radius: 2px;
        margin: 0.6rem auto 2rem;
      }
      .pf-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1.5rem;
      }
      .pf-card {
        background: #fff;
        border: 1px solid #e5e5e5;
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(0,0,0,.06);
        transition: transform .2s, box-shadow .2s;
        text-decoration: none;
        color: inherit;
        display: flex;
        flex-direction: column;
      }
      .pf-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,.12);
      }
      .pf-thumb-wrap {
        position: relative;
        padding-top: 56.25%;
        background: #111;
        overflow: hidden;
      }
      .pf-thumb-wrap img {
        position: absolute;
        inset: 0;
        width: 100%; height: 100%;
        object-fit: cover;
        transition: transform .3s;
      }
      .pf-card:hover .pf-thumb-wrap img { transform: scale(1.04); }
      .pf-play {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0,0,0,.25);
        transition: background .2s;
      }
      .pf-card:hover .pf-play { background: rgba(0,0,0,.4); }
      .pf-play-icon {
        width: 52px; height: 52px;
        background: #e67e22;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.4rem;
        box-shadow: 0 4px 14px rgba(0,0,0,.3);
      }
      .pf-type-badge {
        position: absolute;
        top: 10px; left: 10px;
        background: #e67e22;
        color: #fff;
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .06em;
        padding: 3px 8px;
        border-radius: 20px;
      }
      .pf-type-badge.short { background: #ff0000; }
      .pf-body {
        padding: 1rem 1.1rem 1.2rem;
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
      }
      .pf-card-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 1.35;
        color: #1a1a1a;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      .pf-meta {
        font-size: 0.75rem;
        color: #888;
        margin-top: auto;
        padding-top: 0.4rem;
      }
      .pf-yt-link {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-top: 1.5rem;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.82rem;
        font-weight: 700;
        color: #e67e22;
        text-decoration: none;
        transition: color .2s;
      }
      .pf-yt-link:hover { color: #d35400; }
      .pf-loading {
        text-align: center;
        padding: 2rem;
        color: #999;
        font-size: 0.9rem;
      }
      @media (max-width: 600px) {
        .pf-grid { grid-template-columns: 1fr; }
      }
    `;
    document.head.appendChild(style);
  }

  // ── Créer le conteneur si absent ────────────────────────────────────────────
  function getContainer() {
    let el = document.getElementById(containerId);
    if (!el) {
      el = document.createElement('div');
      el.id = containerId;
      script.parentNode.insertBefore(el, script.nextSibling);
    }
    return el;
  }

  // ── Filtrage par mots-clés ───────────────────────────────────────────────────
  function matchesKeywords(video) {
    if (!keywords.length) return true;
    const haystack = [
      video.title || '',
      video.description || '',
      video.tags ? video.tags.join(' ') : ''
    ].join(' ').toLowerCase();
    return keywords.some(k => haystack.includes(k));
  }

  // ── Formater la date ─────────────────────────────────────────────────────────
  function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  // ── Construire le HTML d'une carte ──────────────────────────────────────────
  function buildCard(video) {
    const videoId = video.video_id || video.id || '';
    const url = `https://www.youtube.com/watch?v=${videoId}`;
    const thumb = video.thumbnail || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
    const isShort = video.type === 'short';
    const typeLabel = isShort ? 'Short' : 'Vidéo';
    const date = formatDate(video.published_at || video.date || '');

    return `
      <a class="pf-card" href="${url}" target="_blank" rel="noopener noreferrer">
        <div class="pf-thumb-wrap">
          <img src="${thumb}" alt="${(video.title || '').replace(/"/g, '&quot;')}" loading="lazy">
          <div class="pf-play">
            <div class="pf-play-icon">▶</div>
          </div>
          <span class="pf-type-badge ${isShort ? 'short' : ''}">${typeLabel}</span>
        </div>
        <div class="pf-body">
          <div class="pf-card-title">${video.title || 'Vidéo LCDMH'}</div>
          ${date ? `<div class="pf-meta">📅 ${date}</div>` : ''}
        </div>
      </a>
    `;
  }

  // ── Rendu principal ──────────────────────────────────────────────────────────
  function render(videos) {
    const container = getContainer();
    const filtered = videos.filter(matchesKeywords).slice(0, maxVideos);

    if (!filtered.length) {
      container.innerHTML = '';
      return;
    }

    // Trier : vidéos longues en premier, puis shorts
    filtered.sort((a, b) => {
      if (a.type === b.type) return 0;
      return a.type === 'short' ? 1 : -1;
    });

    const channelUrl = 'https://www.youtube.com/@LCDMH';

    container.innerHTML = `
      <div class="pf-section">
        <div class="pf-title">Mes vidéos sur <em>KOMOBI</em></div>
        <div class="pf-bar"></div>
        <div class="pf-grid">
          ${filtered.map(buildCard).join('')}
        </div>
        <div style="text-align:center">
          <a class="pf-yt-link" href="${channelUrl}" target="_blank" rel="noopener">
            ▶ Voir toutes mes vidéos sur YouTube
          </a>
        </div>
      </div>
    `;
  }

  // ── Chargement du JSON ───────────────────────────────────────────────────────
  function init() {
    const container = getContainer();
    container.innerHTML = '<div class="pf-loading">Chargement des vidéos…</div>';

    fetch(VIDEOS_JSON + '?v=' + Date.now())
      .then(res => {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(data => {
        // Accepte { videos: [...] } ou directement un tableau
        const videos = Array.isArray(data) ? data : (data.videos || data.items || []);
        render(videos);
      })
      .catch(() => {
        // Silencieux en prod — pas de message d'erreur visible
        container.innerHTML = '';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
