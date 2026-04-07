/**
 * LCDMH — Chargeur de navigation dynamique
 * 
 * Ce script charge nav.html depuis la racine du site et l'injecte
 * en haut de chaque page. Il corrige automatiquement les chemins
 * relatifs selon la profondeur de la page dans l'arborescence.
 * 
 * Usage : ajouter dans le <head> ou juste avant </body> :
 *   <script src="/js/lcdmh-nav-loader.js" defer></script>
 * 
 * Fonctionnement :
 * 1. Fetch /nav.html
 * 2. Corrige les href relatifs (index.html → /index.html)
 * 3. Injecte le HTML en premier enfant de <body>
 * 4. Active le hamburger menu (mobile)
 * 5. Active les dropdowns (clic sur mobile, hover sur desktop)
 * 6. Marque le lien actif dans la nav
 */
(function () {
  "use strict";

  // ── Google Analytics 4 ──
  (function() {
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=G-5DP7XR1C7W";
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag("js", new Date());
    gtag("config", "G-5DP7XR1C7W");
  })();


  // ── Configuration ──
  var NAV_URL = "/nav.html";

  // ── Charger et injecter ──
  if (document.querySelector("nav, #lcdmh-nav, .nav-links, #lcdmh-nav-wrapper")) { return; } fetch(NAV_URL, { cache: "no-cache" })
    .then(function (res) {
      if (!res.ok) throw new Error("nav.html introuvable (" + res.status + ")");
      return res.text();
    })
    .then(function (html) {
      // Corriger les href relatifs → absolus depuis la racine
      // Ex: href="index.html" → href="/index.html"
      // Mais garder les href absolus (http, https, /, #, mailto, tel)
      html = html.replace(
        /href="(?!https?:\/\/|\/|#|mailto:|tel:)([^"]+)"/g,
        'href="/$1"'
      );

      // Supprimer l'ancien bandeau "Menu temporairement indisponible" s'il existe
      var oldBanner = document.querySelector('.topbar, [class*="menu-temp"], [style*="Menu temporairement"]');
      if (oldBanner) oldBanner.remove();

      // Injecter en premier enfant de body
      var wrapper = document.createElement("div");
      wrapper.id = "lcdmh-nav-wrapper";
      wrapper.innerHTML = html;
      document.body.insertBefore(wrapper, document.body.firstChild);

      // ── Hamburger toggle (mobile) ──
      var toggle = document.getElementById("lcdmh-menu-toggle");
      var links = document.getElementById("lcdmh-nav-links");

      if (toggle && links) {
        toggle.addEventListener("click", function () {
          var isOpen = links.classList.toggle("active");
          toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
          toggle.textContent = isOpen ? "✕" : "☰";
        });
      }

      // ── Dropdowns ──
      var dropItems = document.querySelectorAll("#lcdmh-nav .lcdmh-has-drop");
      dropItems.forEach(function (item) {
        var trigger = item.querySelector("[data-nav-trigger]");
        if (!trigger) return;

        trigger.addEventListener("click", function (e) {
          // Sur mobile (< 1100px) → toggle open/close
          if (window.innerWidth <= 1100) {
            e.preventDefault();
            // Fermer les autres
            dropItems.forEach(function (other) {
              if (other !== item) other.classList.remove("open");
            });
            item.classList.toggle("open");
            var expanded = item.classList.contains("open");
            trigger.setAttribute("aria-expanded", expanded ? "true" : "false");
          }
        });
      });

      // Fermer le menu mobile quand on clique sur un lien
      var navLinks = document.querySelectorAll("#lcdmh-nav-links a:not([data-nav-trigger])");
      navLinks.forEach(function (link) {
        link.addEventListener("click", function () {
          if (links) links.classList.remove("active");
          if (toggle) {
            toggle.setAttribute("aria-expanded", "false");
            toggle.textContent = "☰";
          }
        });
      });

      // ── Marquer le lien actif ──
      var currentPath = window.location.pathname;
      var allLinks = document.querySelectorAll("#lcdmh-nav a[href]");
      allLinks.forEach(function (a) {
        var href = a.getAttribute("href");
        if (!href || href === "#") return;
        // Normaliser : /roadtrips/xxx.html → match "roadtrips"
        if (currentPath === href || currentPath.endsWith(href)) {
          a.classList.add("active");
        }
        // Match partiel pour les sections (ex: /articles/xxx → "articles.html")
        var section = href.replace("/", "").replace(".html", "");
        if (section && currentPath.includes("/" + section + "/")) {
          a.classList.add("active");
        }
      });
    })
    .catch(function (err) {
      console.warn("[LCDMH Nav] " + err.message);
      // Fallback minimal si nav.html est inaccessible
      var fallback = document.createElement("div");
      fallback.style.cssText =
        "background:#e67e22;color:#fff;text-align:center;padding:10px;font-family:sans-serif;font-size:14px;";
      fallback.innerHTML =
        'Menu temporairement indisponible — <a href="/" style="color:#fff;text-decoration:underline">Accueil</a>';
      document.body.insertBefore(fallback, document.body.firstChild);
    });
})();
