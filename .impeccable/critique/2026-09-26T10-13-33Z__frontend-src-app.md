---
target: frontend/src/app
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
target_identity: "file:D:\\Bytenorth\\entreprise\\veille\\veille-site\\frontend\\src\\app"
timestamp: 2026-09-26T10-13-33Z
slug: frontend-src-app
---
Method: dual-agent (A: revue design · B: détecteur + navigateur)

## Score de santé (Nielsen)

| # | Heuristique | Note | Problème clé |
|---|---|---|---|
| 1 | État du système | 2 | Écran vide pendant la vérification de session ; aucune fraîcheur du fil ; « En attente » sans échéance |
| 2 | Langage réel | 3 | Messages de validation serveur et last_error bruts |
| 3 | Contrôle et liberté | 2 | Pas d'annulation ; rôle changé au change ; expiration sans retour |
| 4 | Cohérence | 2 | « Thèmes » filtre et gestion ; .btn-link sans font ; .panel dupliqué |
| 5 | Prévention d'erreur | 2 | confirm natif pour cascade ; rôle sans confirmation ; thèmes tous bleus |
| 6 | Reconnaissance | 3 | Titre à un seul filtre ; nom du thème absent de l'article |
| 7 | Flexibilité | 2 | Pas de filtre source, pas de raccourcis, recherche Entrée seulement |
| 8 | Minimalisme | 3 | Propre, frôle le fade en sombre |
| 9 | Récupération d'erreur | 2 | Erreurs non liées aux champs |
| 10 | Aide | 2 | Aucun guidage au premier lancement |
| Total | | 23/40 | Acceptable |

## Spécificité
À moitié ancré : fil par jour, serif de lecture, liseré thème, compteur d'erreurs, « En pause : n8n ne relève pas ces sources ». Reste générique back-office. Les six types de veille n'ont aucune identité visuelle ; le rythme de relevé 2 h est invisible.
Détecteur : 1 constat side-tab feed.page.css:37, faux positif (encodage de donnée) mais seul canal du thème (P2). Injection navigateur bloquée par CSP.

## Problèmes prioritaires
- [P0] /connexion connecté → page noire NG0203 : guards.ts:21-25, inject(Router) après await. Fix : inject avant l'await. Commande : harden.
- [P1] Premier lancement : message « filtres » sans filtre, lecteur invité à ajouter des sources. Fix : 3 états (aucun groupe / sources sans articles / filtres). feed.page.html:66-78. Commande : onboard.
- [P1] Mobile : le rail passe au-dessus du fil (shell.css:105-118). Fix : barre compacte + details natif. Commande : adapt.
- [P1] Expiration de session silencieuse (http.interceptors.ts:49-52). Fix : motif + retour interne. Commande : harden.
- [P2] Thème par couleur seule, défaut #1f4fd1 identique à l'accent. Fix : pastille + nom, palette tournante, garde contraste. Commande : colorize.

## Personas
Alex : pas de filtre source, pas de raccourcis, source non éditable. Sam : focus de route absent, select change = changement de rôle au clavier, bordures 1,4:1, pas d'aria-busy/describedby. Casey : rail avant fil, cibles 20px, formulaire thème nowrap. Éditeur : pas de vue sources en erreur, pas de date de prochain relevé, date courte au lieu de relatif, suppression de thème utilisé échoue après confirmation.

## Mineurs
.btn-link font inherit ; « Thèmes » en double ; types masqués sans groupe ; titre à un filtre ; audit sans état vide ni pagination ; chargement en bas ; .panel dupliqué ; favicon Angular ; texte de base 14px.

## Questions
Types de veille comme signal principal ? Fil en « éditions » de relevé ? Gestes dangereux les moins protégés ?
