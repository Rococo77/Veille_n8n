# Veille — contexte pour Claude Code

Site de veille qui pilote un workflow n8n. Les sources RSS sont rangées en **groupes**.
Chaque groupe a un **type de veille** (enum fixe : technologique, concurrentielle,
reglementaire, securite, marche, autre) et un **thème** (table éditable, avec une couleur).
n8n relève les flux toutes les 2 h et pousse les articles au site. Le site est la source de
vérité ; n8n n'est qu'un worker sans état.

## Stack

- `backend/` : FastAPI, Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic, argon2, pyotp, Fernet.
  - Layout `src/veille/` : `routes/` (fins), `services/` (métier + commit), `models.py`,
    `schemas.py`, `deps.py` (auth/CSRF/rôles), `url_policy.py` (anti-SSRF), `errors.py`
    (Problem Details RFC 9457).
- `frontend/` : Angular 22.
  - Standalone, zoneless, OnPush partout, signals.
  - Lectures via `httpResource`, mutations via services + `firstValueFrom`, jamais de
    `subscribe()` dans les composants.
  - Lire une ressource via `valueOr()` (`core/resource.ts`) : `resource.value()` lève en
    état d'erreur.
- Base : PostgreSQL (Supabase en prod). Les contraintes sont en base (FK, unique, check).

## Déploiement cible

| Composant | Cible | Notes |
|---|---|---|
| Frontend | Vercel, Root Directory `frontend` | `vercel.json` réécrit `/api/*` vers le backend : API same-origin, pas de CORS |
| Backend | Render, offre gratuite, Docker | Le service s'endort après 15 min sans trafic entrant |
| Base | Supabase, pooler en mode **session** (port 5432) + `?ssl=require` | Jamais le mode transaction (6543) : asyncpg y casse sur les requêtes préparées |
| n8n | Auto-hébergé : https://n8n.bytenorth.fr | Accès via le connecteur MCP n8n |

## Invariants de sécurité (zero trust) — ne pas casser

- **Session** : cookie `__Host-veille_session` HttpOnly, Secure, SameSite=Strict.
  - Jeton stocké haché (SHA-256).
  - Expiration après 30 min d'inactivité, et au bout de 12 h dans tous les cas.
  - TOTP obligatoire, avec rotation de session après validation et anti-rejeu par pas de temps.
- **CSRF** : jeton lié à la session dans l'en-tête `X-CSRF-Token`, plus `application/json`
  imposé sur toutes les mutations (middleware dans `main.py`).
- **Rôles** (`viewer` < `editor` < `admin`) : vérifiés côté serveur sur chaque endpoint.
  Les gardes Angular ne sont qu'un confort d'interface.
- **n8n → `/api/internal/*`** : jeton Bearer. Le site ne stocke que son SHA-256
  (`VEILLE_INTERNAL_TOKEN_SHA256`). Aucune session utilisateur n'ouvre cette surface.
  Aucun filtrage par IP : derrière Vercel/Render, `X-Forwarded-For` est falsifiable.
- **Données des flux** : traitées comme hostiles (`services/ingest.py`).
  - Liens `http(s)` uniquement.
  - HTML retiré.
  - Dates futures ramenées à maintenant.
  - Un article invalide est écarté seul, sans faire échouer le lot.
  - Le dédoublonnage repose sur la contrainte unique `(source_id, link)`.
- **URLs de sources** : doivent résoudre uniquement vers des IP publiques, ports 80/443
  (`url_policy.py`). Sinon n8n devient un relais SSRF.
- **Supabase** : la migration `0002` active RLS sans policy et révoque `anon`/`authenticated`.
  Toute nouvelle table doit suivre la même règle.
- **Secrets TOTP** : chiffrés avec Fernet (`VEILLE_TOTP_ENCRYPTION_KEY`).
- **Journal d'audit** : écrit dans la même transaction que l'action auditée.
- **CSP** (`vercel.json`) : `script-src 'self'` strict. Pas de SRI (il injecterait un importmap
  inline), pas d'`inlineCritical` (il injecterait un `onload` inline).

## Commandes

```bash
# Backend : Postgres local via `docker compose up -d db`
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
VEILLE_TEST_DATABASE_URL=postgresql+asyncpg://veille:veille@127.0.0.1:5432/veille pytest   # 28 tests
ruff check src tests alembic && ruff format --check src tests alembic

# Frontend (Node ≥ 22.22.3 ou 24)
cd frontend && npm ci && npx ng build && npx ng serve   # proxy /api → :8000
```

Les tests tournent sur un vrai Postgres, avec le schéma issu des migrations Alembic.
Ne pas passer à SQLite ni à `create_all`.

## État

- **Fait et vérifié** :
  - Backend complet, 28 tests passent.
  - Build Angular prod OK.
  - Migrations `0001` et `0002`.
- **Déployé (2026-09-25)** :
  - Supabase : projet `veille` (`pcvnjayllvarhqpzhfff`, eu-west-3), rôle `veille_app`, pooler
    session `aws-1-eu-west-3.pooler.supabase.com:5432`. Migrations à `0002`, RLS actif,
    `anon` sans droits. Tables propriété de `veille_app` : le rôle `postgres` (SQL Editor, MCP)
    n'y a pas accès sans `GRANT veille_app TO postgres` + `SET ROLE veille_app`.
  - Render : service `veille-api` (`srv-dar8t4bncjis73cj3400`), Francfort, gratuit,
    https://veille-api-6wcq.onrender.com, branche `main`.
  - Admin `corentin.rossetto@gmail.com` : connexion + 2FA validées dans le navigateur.
  - Recette API de bout en bout sur Render : 29/29 (login, 2FA + rotation, CSRF, rôles, SSRF,
    jeton n8n, ingestion hostile, idempotence, fil filtré, cascade, logout).
- **n8n** :
  - Workflow `FzbwhZhjtlNsdbvm` « Veille RSS → site (zero trust) » : **publié**, credential
    Bearer « Veille site - jeton n8n » (`bslqPTb69Lvn7pBP`) sur les 3 nœuds HTTP. `api_base` =
    URL Render directe.
  - Workflow `QvnqMXLP50qZDhen` « Veille keep-alive Render » : publié (10 min).
  - Ancien workflow `out5DZTK69nHIX9x` (Data Tables) : dépublié.
- **Vercel** : projet `veille-n8n` (équipe `rossettos-projects`), Root Directory `frontend`,
  production = `main`, https://veille-n8n.vercel.app. Le rewrite `/api` → Render marche en
  production. Le connecteur MCP Vercel reste sans droits d'écriture sur l'équipe : passer par
  le dashboard.
- **Render** : auto-deploy « On Commit » configuré mais jamais déclenché par un push (accès de
  l'app GitHub Render au dépôt à vérifier). Déployer à la main via le connecteur en attendant.

## À faire (dans l'ordre)

1. **Render** : vérifier l'app GitHub Render sur le dépôt (auto-deploy).
2. **Recette fonctionnelle** : création thème/groupe/source → premier relevé n8n → fil filtré.
3. **Durcissements** : sémaphore argon2 (64 Mio par vérification sur 512 Mo), verrouillage
   plafonné à ~15 min, purge `articles`/`audit_events` via un endpoint interne appelé par n8n,
   alerte n8n sur échec de push, pare-feu de sortie du conteneur n8n (rebinding DNS et
   redirections contournent `url_policy.py`).

## Points non vérifiés ([PROBABLE])

- Limites actuelles de l'offre gratuite Render (750 h/mois, endormissement après 15 min).
