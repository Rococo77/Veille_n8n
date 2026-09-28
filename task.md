# Veille — reste à faire pour une application complète

État au 2026-09-27. Chaque tâche indique **qui** la fait (toi = action dans un dashboard ou
le navigateur, Claude = code ou vérification) et **quand elle est finie**.

## Où on en est

- En production et vérifié : API Render, front Vercel, base Supabase (migrations `0001` à
  `0003`), workflow n8n publié (relevé toutes les 2 h + purge nocturne).
- Purge nocturne vérifiée le 2026-09-27 à 07:17 UTC : succès, jeton n8n valide.
- **Aucune source n'est encore active** : le relevé de 12:07 UTC renvoie une liste vide. La
  chaîne RSS → site → fil n'a donc jamais tourné en réel.
- Backend : 33 tests. Front : build OK, 6 tests ciblés. CI GitHub Actions verte sur
  `31bc2eb` (backend, image Docker, front).
- Pages secondaires refaites dans le monde « fil de dépêches » (`4321dda`).
- Fuseau du workflow n8n réglé sur `Europe/Paris` et republié (2026-09-28).

---

## P0 — Bloquant pour une app utilisable

### 1. Recette de bout en bout avec un vrai flux
- **Toi** : créer une source RSS publique stable dans un groupe **actif**, source **activée**.
- **Claude** : lancer le workflow et lire l'exécution nœud par nœud (lecture RSS, push,
  `inserted` / `rejected`, statut de la source), puis vérifier le fil, les filtres
  (type, thème, groupe, source, recherche) et le marqueur « Nouveau ».
- Point à surveiller : un flux Atom doit remplir `link` côté n8n.
- **Fini quand** : des articles apparaissent dans le fil, la source affiche « OK », et
  rejouer l'exécution n'insère aucun doublon.

### 2. Tester dans un navigateur les dernières livraisons
- **Toi** : tester sur desktop et sur mobile.
  - Page Compte : déconnexion, et liens admin pour un admin.
  - « Affiner » : le filtre source n'est proposé qu'après le choix d'un groupe.
  - Parcours d'invitation complet : lien → mot de passe → 2FA → fil.
  - « Renvoyer l'invitation » : l'ancien lien est refusé.
- **Toi** : confirmer dans le dashboard Vercel que le déploiement de `9e91f27` est « Ready ».
  Le connecteur Vercel de Claude reçoit une erreur 403 sur l'équipe.
- **Fini quand** : aucun écran cassé, aucune erreur dans la console du navigateur (CSP
  comprise).

### 3. Envoi réel des mails d'invitation (Brevo)
- **Toi** :
  1. Créer le compte Brevo et y ajouter le domaine `bytenorth.fr`.
  2. Dans la zone DNS OVH, ajouter les enregistrements fournis par Brevo : TXT de
     vérification, DKIM, et DMARC s'il est absent.
  3. SPF : **compléter la ligne `v=spf1` existante**, ne jamais en créer une seconde.
  4. Créer la clé API et la mettre dans Render sous `VEILLE_MAIL_API_KEY`.
- **Claude** : après ta première invitation de test, vérifier dans les logs Render le statut
  de l'envoi (jamais le contenu).
- **Fini quand** : le mail arrive en boîte de réception, pas en spam, avec un lien qui
  fonctionne.

---

## P1 — Fonctionnalités prévues

### 4. Alertes Discord « ops » (échecs d'exécution)
- **Claude** :
  - Créer un workflow d'erreur n8n : Error Trigger → requête HTTP vers un webhook Discord.
  - Le déclarer comme `errorWorkflow` de « Veille RSS → site » et du keep-alive.
  - Poser `allowed_mentions: {parse: []}` sur chaque message.
- **Fait (2026-09-28)** : workflow `a1m1gRYXkvifAus5` « Veille alertes ops → Discord »
  publié (Error Trigger → Discord en mode webhook, erreur tronquée à 500 caractères) et
  déclaré `errorWorkflow` du relevé et du keep-alive. Credential saisie par toi.
- Le nœud Discord en mode webhook n'expose pas `allowed_mentions` : chaque `@` du message
  est neutralisé par une espace sans chasse, ce qui casse `@everyone` et `<@id>`.
- **Reste** : le test réel ci-dessous.
- Pourquoi dans n8n : si Render est injoignable, le site ne peut prévenir personne.
- **Fini quand** : couper l'API (ou fausser l'URL) fait arriver un message sur le salon.

### 5. Notifications Discord par utilisateur (nouvelle fournée, sources en erreur)
- **Claude** :
  - Migration (avec RLS et révocation d'`anon`) : webhook chiffré avec Fernet, deux
    préférences (« nouvelles dépêches » ; « sources en erreur », réservée à `editor` et
    au-dessus), date de dernière notification.
  - Page Compte : saisir, tester et supprimer son webhook. Seul l'état « configuré » est
    affiché, jamais l'URL.
  - Seules les URLs `https://discord.com/api/webhooks/{id}/{token}` sont acceptées.
  - Nouvel endpoint `POST /api/internal/runs/complete`, appelé par n8n en fin de relevé. Le
    site calcule, pour chaque utilisateur, ce qui est arrivé depuis sa dernière notification.
  - Contenu du message : nombre de dépêches par type de veille, quelques titres, lien vers
    le fil.
  - Les titres viennent des flux, donc sont hostiles : neutraliser le markdown, tronquer,
    et toujours poser `allowed_mentions: {parse: []}`.
  - Envois en parallèle avec timeout. Un webhook qui renvoie 404 est marqué invalide et
    ne fait jamais échouer l'appel de n8n.
- **Fini quand** : un relevé qui apporte des articles notifie chaque utilisateur abonné,
  une seule fois.

### 6. CI GitHub Actions (priorité relevée : la prod a cassé le 2026-09-27)
- **Fait (2026-09-28)** : `.github/workflows/ci.yml` (run #1 vert) et ruleset « gk » actif
  sur `main` : checks `backend`, `docker`, `frontend` requis, force push et suppression
  interdits, aucune exemption. Tout changement passe donc par une branche + PR.
- Ancienne consigne : protéger `main` (merge seulement si la CI est verte). Aujourd'hui, tout push sur
  `main` part directement en production.
- **Fini quand** : une PR qui casse l'image Docker est bloquée avant d'arriver sur `main`.

### 7. Pare-feu de sortie du conteneur n8n
- **Toi et Claude** : sur le VPS, interdire au conteneur n8n de joindre les plages
  privées : RFC 1918, `127.0.0.0/8`, `169.254.0.0/16` (métadonnées cloud), les réseaux
  Docker, et les services Coolify.
- Pourquoi : `url_policy.py` valide l'URL au moment de sa création, mais le rebinding DNS
  et les redirections HTTP la contournent au moment du relevé.
- **Fini quand** : une source qui redirige vers `http://169.254.169.254/` échoue côté n8n.

---

## P2 — Qualité et finition

### 8. Design : clôturer le contrat « fil de dépêches »
- Faire la revue finale prévue par `.impeccable/surfaces/frontend-src-app.md` et écrire
  `DESIGN.md`.
- Trancher la barre d'onglets mobile : le contrat dit Fil / Affiner / Groupes / Compte, le
  code a Thèmes à la place d'Affiner.

### 9. Tests front ciblés — fait (`31bc2eb`, 6 tests : `guestOnly`, `FeedStore`, `LastVisit`, invitation)

### 10. Exploitation
- Fait : procédures dans `docs/exploitation.md` (dump hebdo depuis le VPS, test de
  restauration, rotation de chaque secret). Advisors Supabase relancés après `0003` : seul
  l'INFO « RLS sans policy » attendu. Fuseau n8n `Europe/Paris`.
- **Toi** : poser le script et la crontab sur le VPS, puis faire le test de restauration
  une fois.
- **Fini quand** : un dump restauré en local donne la bonne version Alembic et les bons
  comptes.

### 11. Documentation (dossier EPSI)
- README : schéma d'architecture, flux d'authentification (mot de passe → TOTP → rotation),
  modèle de menaces, choix justifiés (Brevo plutôt que SMTP, Discord émis depuis le site
  plutôt que depuis n8n, invitation plutôt que mot de passe provisoire).
- `PRODUCT.md` : mettre à jour « Evidence on Hand » (thèmes et groupes existent désormais).

---

## Hors périmètre, à décider (non demandé)

- « Mot de passe oublié » en libre-service. Aujourd'hui, c'est l'admin qui renvoie un lien.
  À faire seulement une fois Brevo en place, avec une réponse identique que le compte
  existe ou non.
- Articles lus, favoris, export.
- Relevé déclenché à la demande depuis l'interface. Aujourd'hui, un relevé toutes les 2 h
  et rien d'autre, c'est volontaire.
