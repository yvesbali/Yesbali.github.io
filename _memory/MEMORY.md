# MÉMOIRE LCDMH — Index Cowork
> Dernière mise à jour : 17 avril 2026
> À lire en début de session pour reprendre le contexte sans re-demander.

## Qui est Yves ?
Yves Vella — motard, YouTubeur, créateur de contenu. Base : Annecy, France.
Chaîne YouTube : [@LCDMH](https://www.youtube.com/@LCDMH) (La Chaîne du Motard Heureux)
Site : **lcdmh.com** — GitHub Pages, dépôt `yvesbali/Yesbali.github.io`
Email : yvesbali@gmail.com

## Noms de session
- **Cowork** = moi (l'IA dans Cowork desktop)
- **Claude** = l'autre Claude (version web, souvent Opus 4.7) qui travaille en parallèle

---

## Fichiers mémoire

- [regles.md](regles.md) — Règles LCDMH absolues (RÈGLE N°1 UTF-8, etc.)
- [site.md](site.md) — Structure du site, pages clés, architecture
- [affilies.md](affilies.md) — Partenaires affiliés, codes promo, ref codes
- [projet-nettoyage.md](projet-nettoyage.md) — Projet "Optimisation SEO site" — plan complet (audit avril 2026)
- [workflows.md](workflows.md) — Workflows GitHub Actions actifs
- [articles.md](articles.md) — État des 27 articles (photos, statut, priorités)

---

## Contexte rapide à retenir

**Dépôt Git :** F:\LCDMH_GitHub_Audit (= /sessions/.../mnt/LCDMH_GitHub_Audit)
**Branche active :** main
**Push :** Yves fait toujours `git push origin main` depuis son terminal Windows
**Cowork ne peut pas push directement** (pas de credentials HTTPS dans le sandbox)
**Workaround commit :** git write-tree → commit-tree → écriture directe dans .git/refs/heads/main (les lock files FUSE bloquent git update-ref)

**App Streamlit :** F:\LCDMH_GitHub_Audit (dossier Automate_YT) → app.py
- Déployer les modifications comme fichier `_NEW.py` sauf si explicitement demandé autrement
