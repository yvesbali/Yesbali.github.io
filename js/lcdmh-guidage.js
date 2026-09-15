/* ═══════════════════════════════════════════════════════════════════
   LCDMH — MOTEUR DE GUIDAGE · js/lcdmh-guidage.js
   Prototype /pneus.html · 15/09/2026 · v1.0

   RESPONSABILITÉ UNIQUE :
   lire le bloc « guidage » d'un JSON de page et le rendre dans le
   conteneur #lcdmh-guidage. Rien d'autre.

   Ce que ce fichier NE fait PAS :
   - il ne calcule aucune recommandation (aucun scoring, aucun mot-clé)
   - il ne connaît aucune autre page du site
   - il ne s'applique qu'aux pages qui l'appellent explicitement
   - il ne remplace pas page-content.js et n'en dépend pas

   PROGRESSIVE ENHANCEMENT :
   conteneur absent -> rien. JSON absent/invalide -> rien.
   Toute erreur -> la section reste masquée, la page reste intacte.

   TRACKING : envoi via le système analytics DÉJÀ chargé (gtag / GTM).
   Événements : next_step_choice (choix), internal_nav (pont + étape),
   youtube_click (lien vidéo). Paramètres : page_source, choice_label,
   page_target, intent. Replis : gtag -> dataLayer -> console.
   ?gd_debug=1 dans l'URL active debug_mode pour GA4 DebugView.
   Un échec de mesure ne casse jamais la page.

   Aucune dépendance. Aucune bibliothèque.
   ═══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var C = document.getElementById('lcdmh-guidage');
  if (!C) return;                        // pas de conteneur : aucune action

  var SRC = C.getAttribute('data-json');
  if (!SRC) return;                      // pas de source : aucune action

  /* ---------- Utilitaires ---------- */

  // Échappement : toute valeur venant du JSON passe par ici avant insertion
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // URL : interne (commence par /) ou externe https — sinon rejetée
  function safeUrl(u) {
    if (typeof u !== 'string') return null;
    u = u.trim();
    if (u.charAt(0) === '/' && u.charAt(1) !== '/') return u;
    if (/^https:\/\//i.test(u)) return u;
    return null;
  }

  // ID vidéo YouTube : exactement 11 caractères autorisés
  function safeVideo(id) {
    return (typeof id === 'string' && /^[A-Za-z0-9_-]{11}$/.test(id)) ? id : null;
  }

  /* ---------- Journalisation des clics de guidage ----------
     Envoi via le système analytics DÉJÀ chargé par le site (gtag).
     AUCUNE nouvelle architecture, aucun script tiers, aucun cookie en plus.
     • page_source  : la page où se trouve le visiteur (dynamique)
     • choice_label : QUEL choix a été cliqué (texte lisible)
     • page_target  : la destination
     Replis successifs : gtag -> dataLayer (si GTM seul) -> console.
     Un échec de mesure ne doit JAMAIS casser la page. */
  function track(evt, data) {
    var payload = data || {};
    payload.page_source = location.pathname;
    payload.page_title = (document.title || '').substring(0, 100);
    try { console.debug('[lcdmh-guidage]', evt, payload); } catch (e) {}
    try {
      // ?gd_debug=1 dans l'URL -> l'événement devient visible dans GA4 DebugView
      if (/[?&]gd_debug=1/.test(location.search)) payload.debug_mode = true;
      // Envoi IMMÉDIAT (sendBeacon) : un clic de guidage déclenche une navigation.
      // En mode groupé (« batch »), gtag perdrait l'événement au changement de page.
      payload.transport_type = 'beacon';
      if (typeof window.gtag === 'function') {
        window.gtag('event', evt, payload);
      } else if (window.dataLayer && typeof window.dataLayer.push === 'function') {
        window.dataLayer.push(Object.assign({ event: evt }, payload));
      }
    } catch (e) { /* silencieux : la mesure ne casse jamais la navigation */ }
  }

  // Libellé lisible du lien cliqué — pour savoir QUEL choix a été pris
  function labelOf(a) {
    var el = a.querySelector('.gd-step-label, .gd-bridge-txt, .gd-next-txt');
    var txt = el ? el.textContent : a.textContent;
    return (txt || '').replace(/\s+/g, ' ').trim().substring(0, 100);
  }

  // Élément absent ou tableau vide -> on ne rend rien (droit de ne rien afficher)
  function hasArr(a) { return Array.isArray(a) && a.length > 0; }

  /* ---------- Rendu des blocs ---------- */

  // 1. Preuve terrain : facade légère, lecteur créé seulement au clic
  function renderProof(g) {
    var p = g.proof;
    if (!p || typeof p !== 'object') return '';
    var vid = safeVideo(p.video);
    if (!vid) return '';
    var titre = esc(p.titre || 'Voir la vidéo');
    var cta = esc(p.cta || 'Voir la vidéo');
    var yt = 'https://www.youtube.com/watch?v=' + vid;

    var h = '<div class="gd-block" id="gd-proof">'
      + '<h2 class="gd-title">La preuve sur la route</h2>'
      + '<button class="gd-proof" type="button" data-video="' + vid + '"'
      + ' aria-label="Lire la vidéo : ' + titre + '">'
      + '<span class="gd-proof-media">'
      + '<img src="https://i.ytimg.com/vi/' + vid + '/hqdefault.jpg"'
      + ' alt="" width="480" height="270" loading="lazy" decoding="async">'
      + '<span class="gd-proof-play" aria-hidden="true">▶</span>'
      + '</span>'
      + '<span class="gd-proof-body">'
      + '<span class="gd-proof-titre">' + titre + '</span>'
      + '<span class="gd-proof-cta">' + cta + ' &rsaquo;</span>'
      + '</span></button>'
      + '<a class="gd-proof-yt" href="' + yt + '" target="_blank" rel="noopener">'
      + 'Voir sur YouTube ↗</a>'
      + '</div>';
    return h;
  }

  // 2. Les 3 choix d'usage (maximum 3, jamais plus)
  function renderSteps(g) {
    var st = g.next_steps;
    if (!hasArr(st)) return '';
    var q = esc(g.next_question || 'Et maintenant ?');
    var h = '<div class="gd-block"><h2 class="gd-title">' + q + '</h2><div class="gd-steps">';
    var n = 0;
    for (var i = 0; i < st.length && n < 3; i++) {
      var s = st[i] || {};
      var u = safeUrl(s.url);
      if (!u) continue;                  // URL invalide -> on saute l'entrée
      n++;
      var lbl = esc(s.label || '');
      var why = esc(s.why || '');
      var emo = esc(s.emoji || '›');
      var vt = safeVideo(s.video);
      var aria = vt ? ' data-video="' + vt + '"' : '';
      h += '<a class="gd-step" href="' + u + '"' + aria
        + ' data-intent="' + esc(s.intent || '') + '">'
        + '<span class="gd-step-head">'
        + '<span class="gd-step-emoji" aria-hidden="true">' + emo + '</span>'
        + '<span class="gd-step-label">' + lbl + '</span></span>'
        + (why ? '<span class="gd-step-why">' + why + '</span>' : '')
        + '<span class="gd-step-go" aria-hidden="true">Découvrir ›</span>'
        + '</a>';
    }
    if (!n) return '';
    return h + '</div></div>';
  }

  // 3. Pont voyage
  function renderBridge(g) {
    var b = g.voyage_bridge;
    if (!b) return '';
    var u = safeUrl(b.url);
    if (!u || !b.texte) return '';
    return '<div class="gd-block"><a class="gd-bridge" href="' + u + '" data-bridge="1">'
      + '<span class="gd-bridge-txt">' + esc(b.texte) + '</span>'
      + '<span class="gd-bridge-go" aria-hidden="true">→</span></a></div>';
  }

  // 4. Une seule etape suivante plus large
  function renderNext(g) {
    var n = g.next_big_step;
    if (!n) return '';
    var u = safeUrl(n.url);
    if (!u) return '';
    var lbl = esc(n.label || 'Étape suivante');
    return '<div class="gd-block"><a class="gd-next" href="' + u + '" data-next="1">'
      + '<span class="gd-next-txt">' + esc(n.texte || lbl) + '</span>'
      + '<span class="gd-next-go">' + lbl + ' →</span></a></div>';
  }

  /* ---------- Facade vidéo : le lecteur n'est créé qu'au clic ---------- */
  function bindProof() {
    var btn = C.querySelector('.gd-proof');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var id = safeVideo(btn.getAttribute('data-video'));
      if (!id) return;
      track('video_start', { video_id: id, emplacement: 'preuve-terrain', format: 'facade' });
      var f = document.createElement('iframe');
      f.className = 'gd-player';
      f.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0&modestbranding=1';
      f.title = btn.querySelector('.gd-proof-titre')
        ? btn.querySelector('.gd-proof-titre').textContent : 'Vidéo';
      f.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      f.setAttribute('allowfullscreen', '');
      f.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      // Remplacement du bouton par le lecteur, au même endroit
      btn.parentNode.insertBefore(f, btn.nextSibling);
      btn.style.display = 'none';
      // Repli visuel si la vignette ne charge pas (aucune casse de mise en page)
      var img = btn.querySelector('.gd-proof-media img');
      if (img) { img.addEventListener('error', function () { img.style.display = 'none'; }); }
    }, { once: true });
  }

  /* ---------- Journalisation des clics de guidage ---------- */
  function bindTracks() {
    C.addEventListener('click', function (e) {
      var t = e.target;
      while (t && t !== C && t.tagName !== 'A') t = t.parentNode;
      if (!t || t.tagName !== 'A') return;
      if (t.classList.contains('gd-step')) {
        track('next_step_choice', {
          intent: t.getAttribute('data-intent') || '',
          choice_label: labelOf(t),
          page_target: t.getAttribute('href')
        });
      } else if (t.getAttribute('data-bridge')) {
        track('internal_nav', {
          bloc: 'pont-voyage',
          choice_label: labelOf(t),
          page_target: t.getAttribute('href')
        });
      } else if (t.getAttribute('data-next')) {
        track('internal_nav', {
          bloc: 'etape-suivante',
          choice_label: labelOf(t),
          page_target: t.getAttribute('href')
        });
      } else if (t.classList.contains('gd-proof-yt')) {
        var pf = C.querySelector('.gd-proof');
        track('youtube_click', {
          video_id: pf ? pf.getAttribute('data-video') : '',
          emplacement: 'preuve-terrain',
          cta_type: 'lien-direct'
        });
      }
    });
  }

  /* ---------- Anti-empilement : masquer le maillage générique ----------
     RÈGLE GÉNÉRIQUE (v1.0) : si cette page affiche un guidage contextuel,
     le bloc générique « À lire aussi » (maillage.js) est masqué — sinon les
     deux feraient doublon.
     IMPORTANT :
     - le bloc est MASQUÉ, jamais supprimé : les liens restent dans le HTML et
       demeurent visibles par les robots (aucune perte SEO, aucun lien cassé) ;
     - on ne touche PAS à maillage.js ni à ses liens contextuels dans le texte ;
     - le masquage n'a lieu QUE si le guidage s'est réellement rendu (voir plus
       bas) : si le JSON est cassé ou absent, le maillage reste affiché. */
  function masquerMaillageGenerique() {
    var blocs = document.querySelectorAll('.maillage-section');
    for (var i = 0; i < blocs.length; i++) {
      blocs[i].setAttribute('hidden', '');
      blocs[i].setAttribute('aria-hidden', 'true');
      blocs[i].setAttribute('data-masque-par', 'lcdmh-guidage');
    }
    if (blocs.length) {
      try { console.debug('[lcdmh-guidage] maillage generique masque (' + blocs.length + ' bloc(s)) — guidage contextuel actif'); } catch (e) {}
    }
  }

  /* ---------- Chargement et orchestration ---------- */
  fetch(SRC, { cache: 'no-store' })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (d) {
      var g = d && d.guidage;
      if (!g || typeof g !== 'object') return;      // pas de bloc guidage : rien
      var html = renderProof(g) + renderSteps(g) + renderBridge(g) + renderNext(g);
      if (!html) return;                            // tout vide : rien
      C.innerHTML = html;
      C.removeAttribute('hidden');                  // n'apparaît que si rendu
      bindProof();
      bindTracks();
      masquerMaillageGenerique();                   // évite le doublon avec « À lire aussi »
    })
    .catch(function (err) {
      // JSON cassé, 404, erreur réseau : la section reste masquée, page intacte
      try { console.debug('[lcdmh-guidage] non rendu :', err && err.message); } catch (e) {}
    });
})();
