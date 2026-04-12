/**
 * LCDMH — Chargeur de navigation dynamique
 *
 * Ce script charge nav.html depuis la racine du site et l'injecte
 * dans le div #lcdmh-nav de chaque page.
 *
 * Usage : ajouter dans chaque page :
 *   <div id="lcdmh-nav"></div>
 *   <script src="/js/lcdmh-nav-loader.js" defer></script>
 */
(function () {
  "use strict";

  // — Favicon (injecté sur toutes les pages via ce loader) —
  if (!document.querySelector('link[rel="icon"]')) {
    var fav = document.createElement("link");
    fav.rel = "icon";
    fav.type = "image/png";
    fav.href = "/images/favicon.png";
    document.head.appendChild(fav);
    var fav2 = document.createElement("link");
    fav2.rel = "shortcut icon";
    fav2.href = "/favicon.ico";
    document.head.appendChild(fav2);
  }

  // — Configuration —
  var NAV_URL = "/nav.html";

  // — Trouver le conteneur —
  var container = document.getElementById("lcdmh-nav");
  
  // Si pas de conteneur #lcdmh-nav, en créer un au début du body
  if (!container) {
    container = document.createElement("div");
    container.id = "lcdmh-nav";
    document.body.insertBefore(container, document.body.firstChild);
  }
  
  // Si le conteneur a déjà du contenu (menu déjà chargé), ne rien faire
  if (container.innerHTML.trim() !== "") {
    return;
  }

  // — Charger et injecter —
  fetch(NAV_URL, { cache: "no-cache" })
    .then(function (res) {
      if (!res.ok) throw new Error("nav.html introuvable (" + res.status + ")");
      return res.text();
    })
    .then(function (html) {
      // Corriger les href relatifs → absolus depuis la racine
      html = html.replace(
        /href="(?!https?:\/\/|\/|#|mailto:|tel:)([^"]+)"/g,
        'href="/$1"'
      );

      // Injecter dans le conteneur
      container.innerHTML = html;

      // — Hamburger toggle (mobile) —
      var toggle = document.getElementById("lcdmh-menu-toggle");
      var links = document.getElementById("lcdmh-nav-links");

      if (toggle && links) {
        toggle.addEventListener("click", function () {
          var isOpen = links.classList.toggle("active");
          toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
          toggle.textContent = isOpen ? "✕" : "☰";
        });
      }

      // — Dropdowns —
      var dropItems = document.querySelectorAll("#lcdmh-nav .lcdmh-has-drop");
      dropItems.forEach(function (item) {
        var trigger = item.querySelector("[data-nav-trigger]");
        if (!trigger) return;

        trigger.addEventListener("click", function (e) {
          if (window.innerWidth <= 1100) {
            e.preventDefault();
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

      // — Marquer le lien actif —
      var currentPath = window.location.pathname;
      var allLinks = document.querySelectorAll("#lcdmh-nav a[href]");
      allLinks.forEach(function (a) {
        var href = a.getAttribute("href");
        if (!href || href === "#") return;
        if (currentPath === href || currentPath.endsWith(href)) {
          a.classList.add("active");
        }
        var section = href.replace("/", "").replace(".html", "");
        if (section && currentPath.includes("/" + section + "/")) {
          a.classList.add("active");
        }
      });
    })
    .catch(function (err) {
      console.warn("[LCDMH Nav] " + err.message);
      container.innerHTML =
        '<div style="background:#e67e22;color:#fff;text-align:center;padding:10px;font-family:sans-serif;font-size:14px;">' +
        'Menu temporairement indisponible — <a href="/" style="color:#fff;text-decoration:underline">Accueil</a>' +
        '</div>';
    });
})();
