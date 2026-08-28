/* LCDMH — Bandeau promo partenaires (Carpuride -30% / AOOCCI -25%)
 * Injecté avant le footer sur toutes les pages. Lit /data/partenaires.json (source unique).
 * Créé 23/08/2026 — règle Yves : remises visibles en bas de chaque page, un clic = j'en profite.
 */
(function () {
  "use strict";
  function injecter(partenaires) {
    var cibles = ["carpuride", "aoocci"];
    var cartes = "";
    cibles.forEach(function (id) {
      var p = partenaires[id];
      if (!p) return;
      var lien = (p.liens && (p.liens.general || p.liens.site)) || "#";
      var reduc = p.reduction || "";
      var code = p.code_promo || "";
      cartes +=
        '<a href="' + lien + '" target="_blank" rel="noopener" style="display:flex;flex-direction:column;justify-content:center;align-items:center;gap:.35rem;flex:1 1 260px;max-width:340px;padding:1.2rem 1.4rem;background:#fff;border:1px solid var(--border,#ddd);border-radius:14px;text-decoration:none;color:inherit;transition:transform .15s,box-shadow .15s;" onmouseover="this.style.transform=\'translateY(-2px)\';this.style.boxShadow=\'0 6px 18px rgba(0,0,0,.08)\';" onmouseout="this.style.transform=\'\';this.style.boxShadow=\'\';">' +
        '<span style="font-weight:800;font-size:1.05rem;font-family:\'Montserrat\',sans-serif;color:#1a1a1a;">' + p.nom + "</span>" +
        (reduc ? '<span style="font-size:1.9rem;font-weight:900;line-height:1.1;color:var(--orange,#e05a00);font-family:\'Montserrat\',sans-serif;">' + reduc + "</span>" : "") +
        (code ? '<span style="font-size:.85rem;background:#f5f5f5;border:1px dashed #bbb;border-radius:8px;padding:.25rem .6rem;font-weight:700;color:#333;">Code : ' + code + "</span>" : "") +
        '<span style="font-size:.85rem;font-weight:600;color:var(--orange,#e05a00);">J\u2019en profite \u2192</span></a>';
    });
    if (!cartes) return;
    var section = document.createElement("section");
    section.setAttribute("id", "promo-partenaires");
    section.style.cssText = "background:var(--alt,#f4f2ee);border-top:1px solid var(--border,#e3e0da);padding:2rem 6%;";
    section.innerHTML =
      '<div style="max-width:1200px;margin:0 auto;text-align:center;">' +
      '<p style="font-size:.8rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted,#777);font-weight:700;font-family:\'Montserrat\',sans-serif;margin:0 0 1rem;">Partenaires &amp; remises lecteurs LCDMH</p>' +
      '<div style="display:flex;flex-wrap:wrap;gap:1rem;justify-content:center;">' + cartes + "</div>" +
      '<p style="margin:1rem 0 0;"><a href="/codes-promo.html" style="font-size:.82rem;color:var(--muted,#777);text-decoration:underline;">Voir tous les codes promo \u2192</a></p>' +
      "</div>";
    var footer = document.querySelector("footer");
    if (footer && footer.parentNode) {
      footer.parentNode.insertBefore(section, footer);
    } else {
      document.body.appendChild(section);
    }
  }
  fetch("/data/partenaires.json?t=" + Date.now(), { cache: "no-cache" })
    .then(function (r) { return r.json(); })
    .then(function (d) { injecter((d && d.partenaires) || {}); })
    .catch(function () { /* silencieux si JSON indisponible */ });
})();
