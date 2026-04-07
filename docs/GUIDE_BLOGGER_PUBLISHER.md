# 🏍️ LCDMH — Blogger Auto-Publisher — Guide de mise en place

---

## 📁 OÙ COLLER LES 4 FICHIERS

```
Fichier 1 : blogger_publisher.py
→ F:\LCDMH_GitHub_Audit\scripts\blogger_publisher.py

Fichier 2 : blogger-auto-publisher.yml
→ F:\LCDMH_GitHub_Audit\.github\workflows\blogger-auto-publisher.yml

Fichier 3 : articles_published_blogger.json
→ F:\LCDMH_GitHub_Audit\data\articles_published_blogger.json

Fichier 4 : GUIDE_BLOGGER_PUBLISHER.md (ce fichier)
→ F:\LCDMH_GitHub_Audit\docs\GUIDE_BLOGGER_PUBLISHER.md
```

---

## 🔧 ÉTAPE 1 — Copier les fichiers (2 minutes)

1. Ouvre l'explorateur Windows
2. Copie `blogger_publisher.py` dans `F:\LCDMH_GitHub_Audit\scripts\`
3. Copie `blogger-auto-publisher.yml` dans `F:\LCDMH_GitHub_Audit\.github\workflows\`
4. Copie `articles_published_blogger.json` dans `F:\LCDMH_GitHub_Audit\data\`
5. Ouvre PowerShell dans `F:\LCDMH_GitHub_Audit\` :

```powershell
cd F:\LCDMH_GitHub_Audit
git add scripts/blogger_publisher.py
git add .github/workflows/blogger-auto-publisher.yml
git add data/articles_published_blogger.json
git commit -m "feat: ajout Blogger auto-publisher avec tracking UTM"
git push
```

---

## 🔧 ÉTAPE 2 — Créer le scénario Make.com (10 minutes)

### 2a. Créer un nouveau scénario

1. Va sur **make.com** → Create a new scenario
2. Nomme-le : **"LCDMH → Blogger Teaser"**

### 2b. Module 1 : Webhook (réception)

1. Clique **+** → cherche **Webhooks** → **Custom webhook**
2. Clique **Add** → nomme-le "Blogger Publisher LCDMH"
3. **COPIE L'URL DU WEBHOOK** — tu en as besoin à l'étape 3
4. Clique **OK**

### 2c. Module 2 : Blogger (publication)

1. Clique **+** après le webhook → cherche **Blogger**
2. Sélectionne **Create a Post**
3. **Connecte ton compte Google** (celui qui a le blog lcdmh.blogspot.com)
4. Configure les champs :
   - **Blog ID** : sélectionne "LCDMH, La Chaîne Du Motard Heureux"
   - **Title** : `{{1.title}}`
   - **Content** : `{{1.content}}`
   - **Labels** : `{{1.labels}}`
   - **Is Draft** : `{{1.is_draft}}`
5. Clique **OK**

### 2d. Activer le scénario

1. Clique le bouton **ON** en bas à gauche
2. **Sauvegarde** (Ctrl+S)

---

## 🔧 ÉTAPE 3 — Ajouter le secret GitHub (2 minutes)

1. Va sur **github.com/Yesbali/Yesbali.github.io**
2. Clique **Settings** → **Secrets and variables** → **Actions**
3. Clique **New repository secret**
4. Nom : `MAKE_WEBHOOK_BLOGGER`
5. Valeur : **l'URL du webhook Make.com** (copiée à l'étape 2b)
6. Clique **Add secret**

---

## 🔧 ÉTAPE 4 — Tester (3 minutes)

1. Va sur GitHub → **Actions** → **Blogger Auto-Publisher LCDMH**
2. Clique **Run workflow** → **Run workflow**
3. Attends que le workflow passe au vert ✅
4. Vérifie sur **Make.com** → ton scénario doit montrer "1 operation"
5. Vérifie sur **lcdmh.blogspot.com** → un article doit apparaître

---

## 📊 SUIVI DES CLICS — Comment ça marche

Chaque lien dans les teasers contient des **paramètres UTM** :

```
https://lcdmh.com/articles/mon-article.html
  ?utm_source=blogger
  &utm_medium=teaser
  &utm_campaign=lcdmh-blog
  &utm_content=mon-article
```

### Où voir les clics :

**Option 1 — Blogger (immédiat) :**
- Va sur blogger.com → Statistiques → tu verras les vues par article

**Option 2 — Google Analytics (quand GA4 sera installé sur lcdmh.com) :**
- GA4 → Acquisition → Campagnes → filtre "lcdmh-blog"
- Tu verras exactement combien de visiteurs viennent de Blogger

**Option 3 — Google Search Console :**
- GSC → Performance → filtre page → tu verras les articles qui reçoivent du trafic

### Commande pour voir les stats en local :

```powershell
cd F:\LCDMH_GitHub_Audit
python scripts/blogger_publisher.py --stats
```

---

## 📅 PLANNING AUTOMATIQUE

| Jour     | Heure (Paris) | Action                          |
|----------|---------------|---------------------------------|
| Mardi    | 12h00         | Publication article suivant     |
| Vendredi | 12h00         | Publication article suivant     |

**9 articles disponibles = ~4,5 semaines de contenu**

Chaque nouvel article créé via la Content Factory et ajouté à articles.html
sera automatiquement pris en compte par le script.

---

## 🛠️ COMMANDES UTILES

```powershell
# Voir tous les articles et leur statut
python scripts/blogger_publisher.py --list

# Simuler la publication du prochain article (sans envoyer)
python scripts/blogger_publisher.py --dry-run

# Forcer la publication d'un article spécifique
python scripts/blogger_publisher.py --force aferiy-nano-100-autonomie-electrique-en-road-trip

# Voir les stats de publication
python scripts/blogger_publisher.py --stats
```

---

## ⚠️ POINTS IMPORTANTS

- Les teasers ne contiennent PAS de liens affiliés (RÈGLE N°2)
- Les visiteurs cliquent le CTA pour lire l'article complet sur lcdmh.com
- Les articles sont publiés directement (pas en brouillon) — change `is_draft` dans le script si tu préfères des brouillons
- Le fichier de tracking empêche les doublons : un article n'est publié qu'une seule fois
- Les UTM permettent de mesurer exactement combien de clics chaque article Blogger génère vers lcdmh.com
