# Règles d'édition du site lcdmh.com

Ces règles existent pour éviter que des incidents comme celui du formulaire contact
collé par erreur dans articles.html ne se reproduisent.

## 1. Un seul endroit édite à la fois
Si tu édites sur ton PC pendant que Claude modifie le même fichier, on crée un conflit Git.
On se met d'accord avant chaque session : soit tu édites, soit Claude. Jamais les deux en parallèle.

## 2. Toujours `git pull` avant de commencer
Avant chaque session, lance dans PowerShell (F:\LCDMH_GitHub_Audit) :
```
git pull origin main
```
Ça garantit que la copie locale est à jour avec GitHub.

## 3. Pas de `Set-Content` PowerShell sur les fichiers HTML sensibles
L'opération `Set-Content -Encoding UTF8` peut tronquer un fichier ou casser l'encodage.
Pour tout remplacement de masse (ex : changer un ID GA sur plusieurs pages),
demander à Claude de le faire avec un vrai script Python qui préserve la taille
et l'encodage d'origine.

## 4. Ne jamais éditer articles.html (ni pages critiques) dans l'éditeur GitHub en ligne
L'éditeur web de GitHub ne signale pas toujours les conflits correctement.
Toute modification passe par PowerShell + Claude localement.

## 5. En cas de conflit Git : stop, montrer avant de résoudre
Dès qu'un fichier contient `<<<<<<<`, `=======`, `>>>>>>>`, Claude doit :
- Comparer avec `git show <commit>:<fichier>` pour identifier la version légitime
- Demander validation avant de supprimer quoi que ce soit
- Ne jamais se contenter de retirer les marqueurs en laissant du code « orphelin »

## 6. Vérification systématique après chaque push
Après chaque push vers `origin/main` :
- Ouvrir la page concernée sur lcdmh.com
- Ouvrir la console (F12 → onglet Console)
- Signaler toute erreur immédiatement (pas plusieurs jours après)

## 7. Règle anti-propagation
Si Claude rencontre du code qui semble déplacé (ex : un formulaire contact
sur une page articles, des fonctions orphelines, des variables non définies),
il doit s'arrêter et demander :
« Est-ce que ce code est censé être ici ? »
plutôt que de bricoler autour pour faire taire l'erreur.

## 8. Toutes les opérations Git passent par PowerShell
À cause de la corruption d'index Windows/Linux, les commandes `git add/commit/push`
sont lancées par toi dans PowerShell, pas depuis l'environnement Claude.
Claude prépare les fichiers, tu lances le push.

## 9. Pas de réponses inventées
Préférence utilisateur permanente : Claude ne doit jamais inventer de réponse
ni mentir pour couvrir une incertitude. Si Claude ne sait pas, il le dit.

## 10. Scripting défensif OBLIGATOIRE pour toute opération multi-pages
Aucun script ne doit appliquer un remplacement « aveugle » à plusieurs pages
en supposant qu'elles sont toutes identiques. C'est ce qui a produit aujourd'hui
les doubles footers, les vignettes cassées et les structures orphelines — des
bugs qui sont passés inaperçus pendant plusieurs cycles de modifications.

Protocole obligatoire pour tout script qui touche > 1 page HTML :

### Étape 1 — Scan préalable (lecture seule)
Le script lit CHAQUE page et enregistre en mémoire :
- Présence / absence du motif à modifier
- Nombre d'occurrences du motif (doit être exactement 1, sauf cas prévu)
- Présence de marqueurs de structure attendus (`</head>`, `</body>`, `<footer>`, etc.)
- Particularités détectées (balises déjà présentes, variantes d'écriture, encodage)

### Étape 2 — Classification des pages
À partir du scan, le script classe chaque page dans 3 listes :
- ✅ Pages conformes au motif → modification appliquée
- ⏭️ Pages déjà à jour (motif cible déjà présent) → ignorées
- ⚠️ Pages à structure particulière → **non modifiées**, listées pour inspection manuelle

### Étape 3 — Rapport avant écriture
Avant d'écrire quoi que ce soit, le script affiche le rapport des 3 listes.
L'utilisateur valide avant que les écritures ne s'exécutent.

### Étape 4 — Écriture seulement sur les pages conformes
Seules les pages de la liste ✅ sont modifiées. Les pages ⚠️ sont traitées
au cas par cas ensuite, pas par le script global.

### Règle d'or
Si tu ne peux pas garantir que le motif sera trouvé **une seule fois et au bon endroit**
sur chaque page cible, tu n'écris PAS le script. Tu traites page par page.

Rappel du contexte : sans ce protocole, on a fait passer 10 fois les mêmes pages
dans des scripts qui introduisaient des bugs silencieux. Seule la détection
humaine visuelle a permis de les repérer. Ce n'est pas acceptable.
