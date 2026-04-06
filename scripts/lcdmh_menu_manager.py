# -*- coding: utf-8 -*-
"""
LCDMH — Menu Manager pour Road Trips
====================================
Gère l'affichage des pages road trip dans le menu de navigation.
- Scanne le dossier roadtrips/ pour trouver les pages existantes
- Compare avec nav.html pour voir lesquelles sont visibles
- Permet d'activer/désactiver l'affichage dans le menu

Usage CLI:
    python lcdmh_menu_manager.py --list              # Liste les pages et leur statut
    python lcdmh_menu_manager.py --enable "slug"     # Active une page dans le menu
    python lcdmh_menu_manager.py --disable "slug"    # Désactive une page du menu
    python lcdmh_menu_manager.py --push              # Push les changements sur GitHub

Usage Streamlit:
    from lcdmh_menu_manager import MenuManager
    manager = MenuManager(repo_path)
    pages = manager.get_all_roadtrip_pages()
    manager.toggle_menu("road-trip-moto-test-2026-3", visible=False)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class RoadTripPage:
    """Représente une page road trip."""
    slug: str
    title: str
    filepath: str
    in_menu: bool
    menu_label: Optional[str] = None


class MenuManager:
    """Gestionnaire du menu navigation pour les pages road trip."""
    
    def __init__(self, repo_path: str = None):
        """
        Initialise le gestionnaire.
        
        Args:
            repo_path: Chemin vers le repo GitHub local.
                      Si None, utilise le répertoire courant.
        """
        if repo_path:
            self.repo_path = Path(repo_path)
        else:
            # Essayer de détecter automatiquement
            self.repo_path = self._detect_repo_path()
        
        self.nav_path = self.repo_path / "nav.html"
        self.roadtrips_dir = self.repo_path / "roadtrips"
    
    def _detect_repo_path(self) -> Path:
        """Détecte automatiquement le chemin du repo."""
        # Chemins possibles
        candidates = [
            Path.cwd(),
            Path("F:/LCDMH_GitHub_Audit"),
            Path(__file__).parent.parent,
        ]
        
        for path in candidates:
            if (path / "nav.html").exists():
                return path
        
        raise FileNotFoundError(
            "Impossible de trouver le repo GitHub. "
            "Spécifiez le chemin avec repo_path="
        )
    
    def get_nav_content(self) -> str:
        """Lit le contenu de nav.html."""
        if not self.nav_path.exists():
            raise FileNotFoundError(f"nav.html introuvable: {self.nav_path}")
        return self.nav_path.read_text(encoding="utf-8")
    
    def save_nav_content(self, content: str) -> None:
        """Sauvegarde le contenu de nav.html."""
        self.nav_path.write_text(content, encoding="utf-8")
    
    def get_pages_in_menu(self) -> Dict[str, str]:
        """
        Retourne les pages road trip actuellement dans le menu.
        
        Returns:
            Dict[slug, label] des pages dans le menu
        """
        content = self.get_nav_content()
        
        # Pattern pour trouver les liens dans le dropdown roadtrips
        # <a href="/roadtrips/xxx.html">Label</a>
        pattern = r'<a\s+href="[/]?roadtrips/([^"]+\.html)"[^>]*>([^<]+)</a>'
        
        pages = {}
        for match in re.finditer(pattern, content, re.IGNORECASE):
            filepath = match.group(1)
            label = match.group(2).strip()
            # Extraire le slug du filepath
            slug = filepath.replace(".html", "")
            pages[slug] = label
        
        return pages
    
    def get_all_roadtrip_files(self) -> List[Tuple[str, str]]:
        """
        Scanne le dossier roadtrips/ pour trouver toutes les pages.
        
        Returns:
            List[(slug, title)] des pages trouvées
        """
        if not self.roadtrips_dir.exists():
            return []
        
        pages = []
        for file in self.roadtrips_dir.glob("*.html"):
            # Ignorer les fichiers journal
            if "-journal" in file.name:
                continue
            
            slug = file.stem
            
            # Extraire le titre de la page
            title = self._extract_page_title(file)
            if not title:
                title = slug.replace("-", " ").title()
            
            pages.append((slug, title))
        
        return sorted(pages, key=lambda x: x[0])
    
    def _extract_page_title(self, filepath: Path) -> Optional[str]:
        """Extrait le titre d'une page HTML."""
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            
            # Chercher <title>...</title>
            match = re.search(r'<title>([^<|]+)', content, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Nettoyer le titre
                title = title.replace(" | LCDMH", "").replace(" - LCDMH", "").strip()
                return title
            
            # Chercher <h1>...</h1>
            match = re.search(r'<h1[^>]*>([^<]+)</h1>', content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            return None
        except Exception:
            return None
    
    def get_all_roadtrip_pages(self) -> List[RoadTripPage]:
        """
        Retourne toutes les pages road trip avec leur statut menu.
        
        Returns:
            List[RoadTripPage] avec toutes les infos
        """
        # Pages dans le menu
        menu_pages = self.get_pages_in_menu()
        
        # Toutes les pages du dossier
        all_files = self.get_all_roadtrip_files()
        
        result = []
        for slug, title in all_files:
            in_menu = slug in menu_pages
            menu_label = menu_pages.get(slug)
            
            result.append(RoadTripPage(
                slug=slug,
                title=title,
                filepath=f"roadtrips/{slug}.html",
                in_menu=in_menu,
                menu_label=menu_label
            ))
        
        return result
    
    def add_to_menu(self, slug: str, label: str = None, emoji: str = "🏍️") -> bool:
        """
        Ajoute une page au menu navigation.
        
        Args:
            slug: Slug de la page (ex: "road-trip-moto-test-2026-3")
            label: Label à afficher (si None, utilise le titre de la page)
            emoji: Emoji à ajouter devant le label
        
        Returns:
            True si ajouté, False sinon
        """
        content = self.get_nav_content()
        
        # Vérifier si déjà présent
        if f'href="/roadtrips/{slug}.html"' in content or f"href=\"roadtrips/{slug}.html\"" in content:
            print(f"   ⚠️ {slug} est déjà dans le menu")
            return False
        
        # Trouver le label si non fourni
        if not label:
            pages = self.get_all_roadtrip_files()
            for s, t in pages:
                if s == slug:
                    label = t
                    break
            if not label:
                label = slug.replace("-", " ").title()
        
        # Construire la ligne à insérer
        menu_label = f"{emoji} {label}" if emoji else label
        new_link = f'        <a href="/roadtrips/{slug}.html">{menu_label}</a>'
        
        # Trouver la position d'insertion (à la fin du dropdown roadtrips)
        # Pattern: dernière ligne avant </div> dans le dropdown roadtrips
        
        # Trouver le bloc dropdown roadtrips
        dropdown_pattern = r'(<div class="lcdmh-dropdown" data-nav-menu="roadtrips">)(.*?)(</div>)'
        match = re.search(dropdown_pattern, content, re.DOTALL)
        
        if match:
            dropdown_start = match.group(1)
            dropdown_content = match.group(2)
            dropdown_end = match.group(3)
            
            # Ajouter le nouveau lien à la fin du dropdown
            new_dropdown_content = dropdown_content.rstrip() + "\n" + new_link + "\n      "
            
            new_content = content.replace(
                match.group(0),
                dropdown_start + new_dropdown_content + dropdown_end
            )
            
            self.save_nav_content(new_content)
            print(f"   ✅ {slug} ajouté au menu")
            return True
        else:
            print(f"   ❌ Dropdown roadtrips non trouvé dans nav.html")
            return False
    
    def remove_from_menu(self, slug: str) -> bool:
        """
        Retire une page du menu navigation.
        
        Args:
            slug: Slug de la page à retirer
        
        Returns:
            True si retiré, False sinon
        """
        content = self.get_nav_content()
        
        # Pattern pour trouver la ligne à supprimer
        # Gère les deux formats possibles (avec ou sans / initial)
        patterns = [
            rf'\s*<a\s+href="[/]?roadtrips/{re.escape(slug)}\.html"[^>]*>[^<]*</a>\s*\n?',
        ]
        
        original_content = content
        for pattern in patterns:
            content = re.sub(pattern, '\n', content, flags=re.IGNORECASE)
        
        if content != original_content:
            # Nettoyer les lignes vides multiples
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
            self.save_nav_content(content)
            print(f"   ✅ {slug} retiré du menu")
            return True
        else:
            print(f"   ⚠️ {slug} n'était pas dans le menu")
            return False
    
    def toggle_menu(self, slug: str, visible: bool, label: str = None, emoji: str = "🏍️") -> bool:
        """
        Active ou désactive une page dans le menu.
        
        Args:
            slug: Slug de la page
            visible: True pour ajouter au menu, False pour retirer
            label: Label personnalisé (optionnel)
            emoji: Emoji (optionnel)
        
        Returns:
            True si changement effectué
        """
        if visible:
            return self.add_to_menu(slug, label, emoji)
        else:
            return self.remove_from_menu(slug)
    
    def git_push(self, message: str = "Update navigation menu") -> bool:
        """
        Commit et push les changements sur GitHub.
        
        Args:
            message: Message de commit
        
        Returns:
            True si succès
        """
        try:
            os.chdir(self.repo_path)
            
            # Add
            result = subprocess.run(
                ["git", "add", "nav.html"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"   ❌ git add failed: {result.stderr}")
                return False
            
            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                    print("   ℹ️ Aucun changement à commiter")
                    return True
                print(f"   ❌ git commit failed: {result.stderr}")
                return False
            
            # Push
            result = subprocess.run(
                ["git", "push"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"   ❌ git push failed: {result.stderr}")
                return False
            
            print("   ✅ Changements pushés sur GitHub")
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur Git: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════
#  FONCTIONS STREAMLIT
# ═══════════════════════════════════════════════════════════════════

def render_streamlit_menu_manager(repo_path: str = None):
    """
    Affiche l'interface Streamlit pour gérer le menu.
    À intégrer dans une page Streamlit existante.
    
    Usage:
        import streamlit as st
        from lcdmh_menu_manager import render_streamlit_menu_manager
        render_streamlit_menu_manager("F:/LCDMH_GitHub_Audit")
    """
    import streamlit as st
    
    st.markdown("### 📍 Gestion du menu Road Trips")
    st.markdown("Active ou désactive l'affichage des pages road trip dans le menu du site.")
    
    try:
        manager = MenuManager(repo_path)
        pages = manager.get_all_roadtrip_pages()
    except Exception as e:
        st.error(f"Erreur: {e}")
        return
    
    if not pages:
        st.info("Aucune page road trip trouvée dans le dossier roadtrips/")
        return
    
    # Afficher chaque page avec un toggle
    changes_made = False
    
    for page in pages:
        col1, col2, col3 = st.columns([0.5, 2.5, 1])
        
        with col1:
            # Toggle
            new_state = st.checkbox(
                "visible",
                value=page.in_menu,
                key=f"menu_{page.slug}",
                label_visibility="collapsed"
            )
        
        with col2:
            status_icon = "✅" if page.in_menu else "❌"
            st.markdown(f"**{status_icon} {page.title}**")
            st.caption(f"`{page.filepath}`")
        
        with col3:
            if new_state != page.in_menu:
                changes_made = True
                if new_state:
                    st.success("→ Activer")
                else:
                    st.warning("→ Désactiver")
    
    st.markdown("---")
    
    # Bouton pour appliquer les changements
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Appliquer les changements", type="primary", disabled=not changes_made):
            with st.spinner("Application des changements..."):
                for page in pages:
                    current_state = st.session_state.get(f"menu_{page.slug}", page.in_menu)
                    if current_state != page.in_menu:
                        success = manager.toggle_menu(page.slug, current_state)
                        if success:
                            action = "activé" if current_state else "désactivé"
                            st.success(f"✅ {page.title} {action}")
                
                # Push sur GitHub
                if manager.git_push("Menu navigation mis à jour"):
                    st.success("✅ Changements publiés sur GitHub!")
                    st.balloons()
                else:
                    st.warning("⚠️ Changements locaux OK, mais push GitHub échoué")
    
    with col2:
        if st.button("🔄 Rafraîchir"):
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="LCDMH Menu Manager - Gère le menu navigation")
    parser.add_argument("--repo", help="Chemin vers le repo GitHub", default=None)
    parser.add_argument("--list", action="store_true", help="Liste toutes les pages et leur statut")
    parser.add_argument("--enable", metavar="SLUG", help="Active une page dans le menu")
    parser.add_argument("--disable", metavar="SLUG", help="Désactive une page du menu")
    parser.add_argument("--push", action="store_true", help="Push les changements sur GitHub")
    parser.add_argument("--label", help="Label personnalisé pour --enable")
    parser.add_argument("--emoji", default="🏍️", help="Emoji pour --enable (défaut: 🏍️)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("LCDMH — Menu Manager")
    print("=" * 60)
    
    try:
        manager = MenuManager(args.repo)
        print(f"📂 Repo: {manager.repo_path}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
    
    # --list
    if args.list or (not args.enable and not args.disable):
        print(f"\n📍 Pages Road Trip:\n")
        pages = manager.get_all_roadtrip_pages()
        
        for page in pages:
            status = "✅ MENU" if page.in_menu else "❌ CACHÉ"
            label_info = f" → \"{page.menu_label}\"" if page.menu_label else ""
            print(f"   {status}  {page.slug}{label_info}")
            print(f"           {page.title}")
        
        print(f"\n   Total: {len(pages)} pages")
        menu_count = sum(1 for p in pages if p.in_menu)
        print(f"   Dans le menu: {menu_count}")
        print(f"   Cachées: {len(pages) - menu_count}")
    
    # --enable
    if args.enable:
        print(f"\n→ Activation de {args.enable}...")
        success = manager.add_to_menu(args.enable, args.label, args.emoji)
        if success and args.push:
            manager.git_push(f"Menu: activation de {args.enable}")
    
    # --disable
    if args.disable:
        print(f"\n→ Désactivation de {args.disable}...")
        success = manager.remove_from_menu(args.disable)
        if success and args.push:
            manager.git_push(f"Menu: désactivation de {args.disable}")
    
    print()


if __name__ == "__main__":
    main()
