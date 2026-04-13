/**
 * LCDMH — Footer Loader
 * Injecte le CSS et le HTML du footer standard sur toutes les pages.
 * Modifie ce fichier une fois → mis à jour partout.
 */
(function () {
  'use strict';

  // ── CSS footer ──────────────────────────────────────────────────────────
  const CSS = `
footer{background:#1a1a1a;color:rgba(255,255,255,.65);padding:2.8rem 6%;margin-top:4rem;text-align:center}
.f-logo{font-family:'Montserrat',Arial,sans-serif;font-size:1.6rem;font-weight:800;color:#fff;display:block;margin-bottom:.3rem}
.f-logo em{font-style:normal;color:#e67e22}
.f-tagline{font-size:.83rem;margin:.4rem 0 0;color:rgba(255,255,255,.45)}
.f-nav{list-style:none;display:flex;flex-wrap:wrap;justify-content:center;gap:.5rem 1.5rem;margin:.8rem 0;padding:0}
.f-nav a{font-size:.8rem;color:rgba(255,255,255,.55);text-decoration:none;transition:color .2s}
.f-nav a:hover{color:#e67e22}
.f-legal{font-size:.76rem;color:rgba(255,255,255,.3);margin-top:1.1rem;line-height:1.7}
`;

  // ── HTML footer ─────────────────────────────────────────────────────────
  function buildFooterHTML(base) {
    return `
<div class="f-logo">LC<em>D</em>MH</div>
<p class="f-tagline">La Chaîne du Motard Heureux · Annecy, France</p>
<ul class="f-nav">
  <li><a href="${base}codes-promo.html">Codes promo</a></li>
  <li><a href="${base}carpuride.html">Carpuride</a></li>
  <li><a href="${base}aferiy.html">AFERIY</a></li>
  <li><a href="${base}komobi.html">Komobi</a></li>
  <li><a href="https://www.youtube.com/@LCDMH" target="_blank" rel="noopener">YouTube</a></li>
  <li><a href="${base}mentions-legales.html">Mentions légales</a></li>
  <li><a href="${base}a-propos.html">À propos</a></li>
</ul>
<p class="f-legal">Ce site contient des liens d'affiliation. Leur utilisation me permet de continuer à produire du contenu gratuit sur YouTube.<br>LCDMH © 2026 – Yves · Annecy, France</p>
`;
  }

  // ── Détecter le chemin de base ──────────────────────────────────────────
  function getBase() {
    const depth = window.location.pathname.split('/').filter(Boolean).length;
    // Racine = 0 ou 1 segment → pas de préfixe
    // Sous-dossier (articles/, roadtrips/) = 2 segments → ../
    return depth >= 2 ? '../' : '';
  }

  // ── Injecter ─────────────────────────────────────────────────────────────
  function init() {
    // 1. CSS
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    // 2. Remplacer/remplir le footer existant
    const footer = document.querySelector('footer');
    if (footer) {
      footer.innerHTML = buildFooterHTML(getBase());
    } else {
      // Créer un footer si absent
      const f = document.createElement('footer');
      f.innerHTML = buildFooterHTML(getBase());
      document.body.appendChild(f);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
