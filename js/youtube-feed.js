/**
 * youtube-feed.js — Flux général LCDMH
 * Usage :
 *   <div id="lcdmh-videos"></div>
 *   <div id="lcdmh-shorts"></div>
 *   <script src="js/youtube-feed.js"></script>
 */
(function () {
  const FEED = "/data/videos.json";

  function fmtDur(s) {
    if (!s) return "";
    return Math.floor(s/60) + ":" + String(s%60).padStart(2,"0");
  }
  function fmtViews(n) {
    if (n >= 1e6) return (n/1e6).toFixed(1)+"M vues";
    if (n >= 1e3) return Math.round(n/1e3)+"K vues";
    return n+" vues";
  }

  function cardVideo(v) {
    const desc = v.description ? `<p class="lc-desc">${v.description}</p>` : "";
    return `<a class="lc-card" href="${v.url}" target="_blank" rel="noopener">
      <div class="lc-thumb-box">
        <img src="${v.thumb}" alt="${v.title}" loading="lazy">
        <span class="lc-dur">${fmtDur(v.duration_s)}</span>
      </div>
      <div class="lc-info">
        <p class="lc-title">${v.title}</p>
        ${desc}
        <span class="lc-meta">${v.published} · ${fmtViews(v.views)}</span>
      </div>
    </a>`;
  }

  function cardShort(v) {
    return `<a class="lc-card lc-card--short" href="${v.short_url}" target="_blank" rel="noopener">
      <div class="lc-thumb-box lc-thumb-box--short">
        <img src="${v.thumb}" alt="${v.title}" loading="lazy">
        <span class="lc-badge">Short</span>
      </div>
      <div class="lc-info">
        <p class="lc-title">${v.title}</p>
        <span class="lc-meta">${v.published} · ${fmtViews(v.views)}</span>
      </div>
    </a>`;
  }

  function injectCSS() {
    if (document.getElementById("lc-style")) return;
    const s = document.createElement("style");
    s.id = "lc-style";
    s.textContent = `
      .lc-section { margin: 1.5rem 0; }
      .lc-section-title {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 1rem;
        border-left: 4px solid #e67e22;
        padding-left: .75rem;
        color: #1a1a2e;
        text-transform: uppercase;
        letter-spacing: .05em;
      }
      .lc-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1.25rem;
        max-width: 1100px;
        margin: 0 auto;
      }
      .lc-grid--shorts {
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        max-width: 1100px;
        margin: 0 auto;
      }
      .lc-card {
        display: flex;
        flex-direction: column;
        background: #fff;
        border: 1px solid #e8e8e8;
        border-radius: 10px;
        overflow: hidden;
        text-decoration: none;
        color: #1a1a2e;
        transition: transform .2s, box-shadow .2s;
      }
      .lc-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,.12);
      }
      .lc-thumb-box {
        position: relative;
        width: 100%;
        padding-top: 56.25%;
        background: #111;
        overflow: hidden;
      }
      .lc-thumb-box--short { padding-top: 177.78%; }
      .lc-thumb-box img {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .lc-dur, .lc-badge {
        position: absolute;
        bottom: 6px;
        right: 8px;
        background: rgba(0,0,0,.8);
        color: #fff;
        font-size: .7rem;
        padding: 2px 6px;
        border-radius: 4px;
      }
      .lc-badge { background: #e67e22; font-weight: 700; }
      .lc-info { padding: .75rem 1rem; flex: 1; }
      .lc-title {
        margin: 0 0 .35rem;
        font-size: .9rem;
        font-weight: 700;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        color: #1a1a2e;
      }
      .lc-desc {
        font-size: .78rem;
        color: #555;
        margin: 0 0 .4rem;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        line-height: 1.4;
      }
      .lc-meta { font-size: .72rem; color: #e67e22; font-weight: 600; }
      .lc-updated { font-size: .7rem; color: #999; margin-bottom: 1rem; text-align: center; }
    `;
    document.head.appendChild(s);
  }

  fetch(FEED)
    .then(r => r.json())
    .then(data => {
      injectCSS();
      const vEl = document.getElementById("lcdmh-videos");
      const sEl = document.getElementById("lcdmh-shorts");
      const upd = (data.updated_at || "").slice(0, 10);

      if (vEl && data.videos && data.videos.length) {
        vEl.innerHTML = `<div class="lc-section">
          <p class="lc-section-title">🎬 Dernières vidéos</p>
          <p class="lc-updated">Mis à jour le ${upd}</p>
          <div class="lc-grid">${data.videos.map(cardVideo).join("")}</div>
        </div>`;
      }
      if (sEl && data.shorts && data.shorts.length) {
        sEl.innerHTML = `<div class="lc-section" style="margin-top:2rem">
          <p class="lc-section-title">⚡ Derniers Shorts</p>
          <div class="lc-grid lc-grid--shorts">${data.shorts.map(cardShort).join("")}</div>
        </div>`;
      }
    })
    .catch(e => console.warn("[LCDMH feed]", e.message));
})();
