/* ═══════════════════════════════════════════════════════════
   LCDMH PARTNERS — bandeau partenaires global (28/08/2026)
   Rendu automatique depuis promos/bons_plans.json (SOURCE UNIQUE)
   Modifier une offre = éditer le JSON, rien d'autre.
   Aucune bibliothèque requise (fetch natif).
   ═══════════════════════════════════════════════════════════ */
(function () {
  var C = document.getElementById('lcdmh-partners');
  if (!C) return;
  fetch('/promos/bons_plans.json', { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var html = '<div class="bp-block">'
        + '<div class="bp-head"><h2>' + d.titre + '</h2><p>' + d.sous_titre + '</p></div>'
        + '<div class="bp-grid">';
      (d.offres || []).forEach(function (o) {
        html += '<a class="bp-card" href="' + o.lien + '" target="_blank" rel="sponsored nofollow noopener">'
          + '<span class="bp-img-wrap"><img class="bp-img" src="' + o.image + '" alt="' + o.alt + '" width="84" height="84" loading="lazy"></span>'
          + '<span class="bp-mid">'
          + '<span class="bp-name">' + o.nom + '</span>'
          + '<span class="bp-texte">' + o.texte + '</span>'
          + '<span class="bp-code">' + o.code_label + ' <strong>' + o.code + '</strong></span>'
          + '</span>'
          + '<span class="bp-btn">' + o.bouton + '</span>'
          + '</a>';
      });
      html += '</div><p class="bp-mention">' + d.mention + '</p></div>';
      C.innerHTML = html;
    })
    .catch(function () { C.innerHTML = ''; });
})();
