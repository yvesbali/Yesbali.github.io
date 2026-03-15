# 📘 GUIDE D'INSTALLATION - Publication Automatique Facebook

## 🎯 Ce que fait ce script

Ce script Python transforme votre bibliothèque de posts programmés en publications automatiques sur Facebook et Instagram.

**Fonctionnalités :**
- ✅ Lit la bibliothèque `facebook_payload_test.json`
- ✅ Trouve le prochain post à publier (selon date/heure)
- ✅ Extrait 2 miniatures YouTube (pour carrousel Instagram)
- ✅ Génère un payload compatible Make
- ✅ Envoie au webhook Make
- ✅ Marque le post comme publié

---

## 📋 ÉTAPE 1 : Installation des prérequis

### Sur votre PC (Windows/Mac/Linux)

```bash
# Installer Python 3.8+ si pas déjà installé
# Télécharger sur https://www.python.org/downloads/

# Installer la librairie requests
pip install requests
```

---

## 📋 ÉTAPE 2 : Configuration du script

### 2.1 - Récupérer l'URL du webhook Make

1. Ouvrez Make.com
2. Allez dans le scénario "Publication Photos&Videos"
3. Cliquez sur le module **Webhook** (le premier, rouge)
4. **Copiez l'URL du webhook** (ex: `https://hook.eu1.make.com/xxxxx`)

### 2.2 - Modifier le script Python

Ouvrez le fichier `facebook_publisher.py` et remplacez cette ligne :

```python
WEBHOOK_URL = "VOTRE_URL_WEBHOOK_MAKE_ICI"  # À remplacer
```

Par votre URL réelle :

```python
WEBHOOK_URL = "https://hook.eu1.make.com/VOTRE_URL_ICI"
```

---

## 📋 ÉTAPE 3 : Structure des fichiers

Placez les fichiers dans le même dossier :

```
📁 mon_projet_lcdmh/
  ├── facebook_publisher.py          ← Le script Python
  ├── facebook_payload_test.json     ← Votre bibliothèque de posts
  └── README.md                       ← Ce guide
```

---

## 📋 ÉTAPE 4 : Test manuel

### Tester le script

```bash
# Dans le terminal, allez dans le dossier
cd chemin/vers/mon_projet_lcdmh

# Exécuter le script
python facebook_publisher.py
```

### Résultat attendu

```
🚀 LCDMH - Publication automatique Facebook
==================================================
📖 Chargement de facebook_payload_test.json...
✅ 26 posts chargés (18 mars 2026 → 14 juin 2026)

🔍 Recherche du prochain post à publier...

📝 Post trouvé:
   ID       : w01-aoocci-u6
   Date     : 2026-03-18 12:00
   Type     : affilie
   Vidéo    : Wjvneq7pk5k
   Catégorie: aoocci

🔧 Génération du payload Make...
✅ Payload créé avec 2 miniatures YouTube

📤 Envoi vers Make...
✅ Publication réussie : w01-aoocci-u6
✅ Post w01-aoocci-u6 marqué comme publié

🎉 Publication terminée avec succès !
```

---

## 📋 ÉTAPE 5 : Automatisation avec GitHub Actions

Pour exécuter ce script automatiquement chaque jour, créez un workflow GitHub :

### Fichier `.github/workflows/facebook-publisher.yml`

```yaml
name: Publication Facebook Programmée

on:
  schedule:
    # Tous les jours à 8h et 12h (UTC)
    - cron: '0 8,12 * * *'
  workflow_dispatch:  # Permet de lancer manuellement

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install requests
      
      - name: Run publisher
        env:
          WEBHOOK_URL: ${{ secrets.MAKE_WEBHOOK_URL }}
        run: |
          python facebook_publisher.py
      
      - name: Commit updated library
        run: |
          git config --global user.name 'GitHub Action'
          git config --global user.email 'action@github.com'
          git add facebook_payload_test.json
          git commit -m "📝 Post publié automatiquement" || echo "Pas de changement"
          git push
```

### Ajouter le secret GitHub

1. Sur GitHub, allez dans **Settings** → **Secrets and variables** → **Actions**
2. Cliquez sur **New repository secret**
3. Nom : `MAKE_WEBHOOK_URL`
4. Valeur : Votre URL webhook Make
5. Sauvegardez

---

## 🔧 DÉPANNAGE

### Erreur : "No module named 'requests'"

```bash
pip install requests
```

### Erreur : "Aucun post à publier"

Vérifiez que la date/heure du post est bien passée :
- Le script compare avec l'heure actuelle
- Format attendu : `"scheduled_date": "2026-03-18", "scheduled_time": "12:00"`

### Erreur 404 sur le webhook

- Vérifiez que l'URL du webhook est correcte
- Vérifiez que le scénario Make est **activé** (ON)

---

## 📊 EXEMPLE DE PAYLOAD GÉNÉRÉ

Le script transforme un post de votre bibliothèque :

```json
{
  "id": "w01-aoocci-u6",
  "video_id": "Wjvneq7pk5k",
  "message": "Un GPS moto à 175€..."
}
```

En payload Make compatible :

```json
{
  "title": "Un GPS moto à 175€...",
  "description": "Un GPS moto à 175€ qui navigue sans réseau...",
  "mediaType": "photos",
  "publish_fb": true,
  "publish_ig": true,
  "photos": [
    {"secure_url": "https://img.youtube.com/vi/Wjvneq7pk5k/maxresdefault.jpg"},
    {"secure_url": "https://img.youtube.com/vi/Wjvneq7pk5k/hqdefault.jpg"}
  ],
  "link_web": "https://lcdmh.com",
  "link_yt": "https://www.youtube.com/watch?v=Wjvneq7pk5k"
}
```

---

## ✅ VÉRIFICATION FINALE

1. ✅ Python 3.8+ installé
2. ✅ `requests` installé (`pip install requests`)
3. ✅ URL webhook configurée dans le script
4. ✅ Fichier `facebook_payload_test.json` dans le même dossier
5. ✅ Scénario Make activé
6. ✅ Filtre Instagram "Min 2 photos" configuré dans Make

---

## 📞 SUPPORT

Si tu as un problème :
1. Vérifie les logs du script
2. Vérifie l'historique d'exécution Make
3. Teste avec un post dont la date est déjà passée

---

Créé pour LCDMH - La Chaîne du Motard Heureux
Date : 15 mars 2026
