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
