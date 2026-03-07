/**
 * trip-feed.js — Page voyage LCDMH
 * Usage :
 *   <div id="trip-videos"></div>
 *   <div id="trip-shorts"></div>
 *   <script>const TRIP_SLUG = "ecosse-irlande-2025";</script>
 *   <script src="js/trip-feed.js"></script>
 */
(function () {
  const slug = window.TRIP_SLUG;
  if (!slug) { console.warn("[trip-feed] TRIP_SLUG non defini"); return; }

  const FEED = `/data/trips/${slug}.json`;

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
    return `<a class="lc-card" href="${v.url}" target="_blank" rel="noopener">
      <div class="lc-thumb-box">
        <img src="${v.thumb}" alt="${v.title}" loading="lazy">
        <span class="lc-dur">${fmtDur(v.duration_s)}</span>
      </div>
      <div class="lc-info">
        <p class="lc-title">${v.title}</p>
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

  fetch(FEED)
    .then(r => r.json())
    .then(data => {
      const vEl = document.getElementById("trip-videos");
      const sEl = document.getElementById("trip-shorts");
      const upd = (data.updated_at || "").slice(0, 10);
      if (vEl && data.videos?.length) {
        vEl.innerHTML = `<div class="lc-section">
          <p class="lc-section-title">🎬 Episodes — ${data.trip_title}</p>
          <p class="lc-updated">Mis a jour le ${upd}</p>
          <div class="lc-grid">${data.videos.map(cardVideo).join("")}</div>
        </div>`;
      }
      if (sEl && data.shorts?.length) {
        sEl.innerHTML = `<div class="lc-section">
          <p class="lc-section-title">⚡ Shorts du voyage</p>
          <p class="lc-updated">${data.shorts.length} Short(s) publie(s)</p>
          <div class="lc-grid lc-grid--shorts">${data.shorts.map(cardShort).join("")}</div>
        </div>`;
      }
    })
    .catch(e => console.warn("[trip-feed]", e.message));
})();
