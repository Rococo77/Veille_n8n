# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Petite équipe ByteNorth. Quelques personnes lisent le fil de veille (rôle `viewer`), une ou
deux gèrent thèmes, groupes et sources (`editor`), une administre les comptes (`admin`).
Le fil se lit autant sur desktop (revue triée, ouverture des articles utiles) que sur mobile
(coup d'œil, lecture entre deux tâches).

## Product Purpose

Centraliser la veille de l'équipe : les flux RSS sont rangés en groupes, chaque groupe a un
type de veille et un thème, et un fil unique présente les articles relevés, filtrables par
angle. Le projet sert aussi de support à un projet scolaire (EPSI) : la démarche d'architecture
et de sécurité doit rester démontrable.

Succès : l'équipe consulte un fil à jour, filtré par angle métier, sans passer par un SaaS tiers.

## Positioning

- **Lecture par angle métier** : chaque groupe porte un type de veille fixe (technologique,
  concurrentielle, réglementaire, sécurité, marché, autre) ; le fil se filtre par type, thème,
  groupe ou source.
- **Auto-hébergé, zero trust** : données chez ByteNorth, 2FA obligatoire, rôles vérifiés côté
  serveur, données des flux traitées comme hostiles.
- **Le site pilote n8n** : le site est la source de vérité, n8n n'est qu'un worker sans état qui
  relève les flux toutes les 2 h ; extensible (enrichissement, alertes) sans toucher au site.

## Operating Context

- Relevé automatique toutes les 2 h par n8n (`n8n.bytenorth.fr`) ; pas de relevé à la demande
  depuis l'interface.
- Frontend Vercel, API Render (offre gratuite, keep-alive n8n), base Supabase.
- Sessions : expiration après 30 min d'inactivité et 12 h maximum ; connexion en deux temps
  (mot de passe puis code TOTP).

## Capabilities and Constraints

- Fil d'articles paginé par curseur, regroupé par jour, filtres type / thème / groupe / source,
  recherche plein texte sur le titre.
- Gestion des thèmes (nom + couleur), groupes (type, thème, description, actif), sources (URL
  RSS, statut du dernier relevé, erreurs consécutives).
- Administration : comptes, rôles, réinitialisation 2FA, déverrouillage, journal d'audit.
- Contraintes : CSP stricte (`script-src 'self'`, pas de script inline) ; les URLs de sources
  doivent résoudre vers des IP publiques ; un article n'a que titre, extrait texte, lien et date
  (pas d'image, pas de contenu complet).
- Types de veille : liste fixe, non éditable. Thèmes : éditables.
- Terminologie : « veille », « groupe », « source », « thème », « type de veille », « relevé ».

## Evidence on Hand

Aucune donnée réelle encore : pas de thème, groupe ni source créés au 2026-09-26. Pas de logo,
pas de charte, pas de témoignage. Ne rien inventer.

## Product Principles

1. **Le fil d'abord** : lire vite et trier par angle est la tâche principale ; la gestion
   (thèmes, groupes, sources) est secondaire et réservée aux éditeurs.
2. **La sécurité ne se négocie pas pour le confort** : pas de raccourci qui affaiblit session,
   2FA, CSRF ou CSP.
3. **Honnête sur l'état des sources** : une source en erreur se voit ; le site ne cache pas les
   échecs de relevé.
4. **Démontrable** : chaque choix doit pouvoir s'expliquer dans le cadre du projet scolaire.
