/* ═══════════════════════════════════════════════════════════
   LCDMH PARTNERS — bandeau partenaires global (28/08/2026)
   Rendu automatique depuis promos/bons_plans.json (SOURCE UNIQUE)
   Modifier une offre = éditer le JSON, rien d'autre.
   Aucune bibliothèque requise (fetch natif).
   ═══════════════════════════════════════════════════════════ */
(function () {
  /* ═══════════════════════════════════════════════════════════
     MESURE DES CLICS PARTENAIRES (15/09/2026)
     Objectif : savoir QUELLE page génère des clics vers les marques,
     donc du revenu potentiel. On utilise le système analytics DÉJÀ
     chargé par le site (gtag). Aucun script tiers, aucun cookie en plus.
     Écouteur global : capte aussi les liens ajoutés dynamiquement
     (bandeau bons plans, bloc guidage).
     ═══════════════════════════════════════════════════════════ */
  var PARTENAIRES = {
    'carpuride.com': 'Carpuride',
    'aoocci.fr': 'Aoocci',
    'olightstore.fr': 'Olight',
    'innovv.com': 'INNOVV',
    'komobi.com': 'Komobi',
    'tidd.ly': '123pneus',
    'blackview.hk': 'Blackview',
    'amazon.fr': 'Amazon',
    'led-colight.com': 'Colight',
    'reurl.cc': 'Colight'
  };
  function partenaireDe(href) {
    for (var d in PARTENAIRES) {
      if (PARTENAIRES.hasOwnProperty(d) && href.indexOf(d) !== -1) return PARTENAIRES[d];
    }
    return null;
  }
  document.addEventListener('click', function (e) {
    var a = e.target;
    while (a && a.tagName !== 'A') a = a.parentNode;
    if (!a || a.tagName !== 'A') return;
    var href = a.getAttribute('href') || '';
    if (!/^https?:\/\//i.test(href)) return;       // lien interne relatif : ignoré
    if (href.indexOf('lcdmh.com') !== -1) return;  // lien interne absolu : ignoré
    var part = partenaireDe(href);
    if (!part) return;                             // pas un partenaire : ignoré
    try {
      var p = {
        partenaire: part,
        page_source: location.pathname,
        page_target: href.substring(0, 300),
        lien_texte: (a.textContent || '').replace(/\s+/g, ' ').trim().substring(0, 100),
        transport_type: 'beacon'                   // envoi immédiat (la page va naviguer)
      };
      if (typeof window.gtag === 'function') {
        window.gtag('event', 'clic_partenaire', p);
      } else if (window.dataLayer && typeof window.dataLayer.push === 'function') {
        window.dataLayer.push(Object.assign({ event: 'clic_partenaire' }, p));
      }
    } catch (err) { /* la mesure ne casse jamais la navigation */ }
  }, true);

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
          + '<span class="bp-img-wrap"><img class="bp-img" src="' + o.image + '" alt="' + o.alt + '" width="64" height="64" loading="lazy"></span>'
          + '<span class="bp-mid">'
          + '<span class="bp-name"><span class="bp-ico" aria-hidden="true">' + (o.icone || '') + '</span>' + o.nom + '</span>'
          + '<span class="bp-texte">' + o.texte + '</span>'
          + '<span class="bp-code">' + o.code_label + ' <strong>' + o.code + '</strong></span>'
          + '</span>'
          + '<span class="bp-btn">' + o.bouton + '</span>'
          + '</a>';
      });
      html += '</div>';
      if (d.cta && d.cta.lien) { html += '<a class="bp-cta" href="' + d.cta.lien + '">' + d.cta.texte + '</a>'; }
      html += '<p class="bp-mention">' + d.mention + '</p></div>';
      C.innerHTML = html;
    })
    .catch(function () { C.innerHTML = ''; });
})();
