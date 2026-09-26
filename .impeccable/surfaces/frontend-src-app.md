---
version: 1
slug: "frontend-src-app"
primary_target: "frontend/src/app"
related_targets: []
---

# Surface : application Veille (frontend/src/app)

Mode : Operate. Équipe ByteNorth, desktop et mobile à égalité ; lecteurs (fil) et éditeurs (groupes, sources, thèmes).
Tâche : lire vite le fil par angle (type de veille), ouvrir les articles utiles, surveiller l'état des sources.
Contraintes : CSP stricte (aucun script inline, polices self-hosted uniquement), pas de mode sombre imposé (clair par défaut, sombre selon le système), aucun ornement type onglet/oreille, alignements rigoureux parent/enfant, mobile pensé au pouce.
Décisions de l'utilisateur : type de veille = structure, thème = détail de couleur.

## Direction contract

THESIS : le fil est un téléscripteur d'agence. Chaque article est une dépêche horodatée, classée par desk (type de veille). Refuse la barre latérale + cartes des lecteurs RSS et le back-office en panneaux.

OWN-WORLD : blanc papier, encre quasi noire, un seul rouge dépêche pour le nouveau, l'actif et l'alerte, gris d'agence pour le secondaire. Heures en chiffres tabulaires dans une colonne fixe, slugs de desk en capitales légèrement espacées, filets pleine largeur de 1 px. Ni carte, ni ombre, ni pastille, ni liseré latéral. Thème = carré de 8 px suivi de son nom.

STORY : on ouvre, on voit le desk actif et les dépêches depuis la dernière visite, marquées NOUVEAU. On change de desk au pouce, on affine si besoin, on ouvre la dépêche.

FIRST VIEWPORT : desktop, bandeau de tête (mot-symbole, desks en rangée, cadence des relevés, compte), puis colonne d'heures et dépêches sur un bord gauche unique, à 68rem max. Mobile, bandeau compact, desks en bande défilante sous le bandeau, fil immédiatement, barre d'onglets en bas (Fil, Affiner, Groupes, Compte). Action primaire : ouvrir une dépêche.

FORM : Fil de dépêches, candidat n°1 de ma liste (pick) ; seed 04fa787a.

FINISH : unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
