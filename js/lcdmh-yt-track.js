/* LCDMH — mesure des clics sortants vers YouTube (19/10/2026)
 *
 * Envoie un événement GA4 "clic_youtube" qui porte DEUX informations que
 * l'événement natif GA4 ne donne pas : la page d'origine et l'identifiant
 * de la vidéo YouTube cliquée.
 *
 * Pas de double comptage :
 *  - l'événement natif de la mesure améliorée GA4 s'appelle "click" et reste
 *    inchangé ; "clic_youtube" est un indicateur distinct, jamais additionné
 *    avec lui ;
 *  - un même clic ne peut pas déclencher deux fois l'événement (verrou de
 *    1,5 s sur le lien cliqué, utile quand un lien est enveloppé dans une
 *    vignette qui écoute aussi le clic).
 *
 * Ne bloque jamais le clic : aucun preventDefault, aucun changement de cible.
 */
(function () {
  if (window.__lcdmhYtTrack) return;
  window.__lcdmhYtTrack = true;

  function idVideo(url) {
    var m = String(url || "").match(
      /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/
    );
    return m ? m[1] : "";
  }

  function emplacement(a) {
    var el = a.closest("section[id],section,header,footer,nav,article");
    if (!el) return "autre";
    return el.id || el.tagName.toLowerCase();
  }

  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest
      ? e.target.closest('a[href*="youtube.com"], a[href*="youtu.be"]')
      : null;
    if (!a) return;
    if (a.dataset.lcdmhYtSent === "1") return;
    a.dataset.lcdmhYtSent = "1";
    setTimeout(function () { a.dataset.lcdmhYtSent = "0"; }, 1500);
    if (typeof gtag !== "function") return;

    var vid = idVideo(a.href);
    gtag("event", "clic_youtube", {
      page_origine: location.pathname,
      video_id: vid || "(chaine ou playlist)",
      type_lien: vid ? "video" : (/[?&]list=/.test(a.href) ? "playlist" : "chaine"),
      emplacement: emplacement(a),
      lien: String(a.href).slice(0, 200)
    });
  }, true);
})();
