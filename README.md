# Veille

Site de veille qui pilote un workflow n8n : les sources sont rangées en **groupes**, chaque
groupe a un **type de veille** (technologique, concurrentielle, réglementaire, sécurité,
marché, autre) et un **thème** libre. n8n relève les flux toutes les 2 h et renvoie les
articles au site.

```
Navigateur ──HTTPS──▶ Vercel (Angular statique + rewrite /api/*) ──HTTPS──▶ Render (FastAPI)
                                                                              │ TLS
n8n (VPS) ──HTTPS + Bearer──────────────────────────────────▶ /api/internal/* ▼
                                                                    Supabase Postgres
```

## Modèle de sécurité (zero trust)

Aucune requête n'est crue sur sa provenance réseau : chacune porte sa propre preuve.

| Surface | Preuve exigée | Détail |
|---|---|---|
| Utilisateurs | Session serveur + TOTP obligatoire | Cookie `__Host-` HttpOnly, Secure, SameSite=Strict ; jeton stocké haché ; expiration 30 min d'inactivité / 12 h absolue ; rotation après le 2FA ; anti-rejeu TOTP |
| Mutations | Jeton CSRF lié à la session + `application/json` imposé | Double barrière : un formulaire cross-site ne passe ni l'une ni l'autre |
| Droits | Rôle vérifié sur **chaque** endpoint | `viewer` < `editor` < `admin` ; les gardes Angular ne sont qu'un confort |
| n8n | Jeton Bearer dédié | Le site ne stocke que son SHA-256 ; ce jeton n'ouvre que `/api/internal/*` et aucune session ne l'ouvre |
| Contenu des flux | Traité comme hostile | Liens `http(s)` uniquement (bloque `javascript:`), HTML retiré, dates futures ramenées, articles invalides écartés un par un |
| URLs de sources | Refus de tout ce qui ne résout pas en IP publique | Sinon n8n devient un relais SSRF vers le VPS (métadonnées cloud, services Coolify) |
| Base Supabase | RLS activé sans policy + `REVOKE` pour `anon`/`authenticated` | Sinon la clé publique Supabase lirait `users` via l'API REST auto-générée |
| Secrets TOTP | Chiffrés (Fernet) | Une fuite de la base seule ne donne pas les seconds facteurs |
| Audit | Journal en base, même transaction que l'action | Connexions, échecs, modifications, relevés en erreur |

## Déploiement

### 1. Supabase

1. Créer le projet dans une région proche de Render (Paris : `eu-west-3`).
2. SQL Editor — rôle applicatif dédié plutôt que `postgres` :

   ```sql
   CREATE ROLE veille_app LOGIN PASSWORD '<mot-de-passe-fort>';
   GRANT USAGE, CREATE ON SCHEMA public TO veille_app;
   ```
3. Connect → **Session pooler** → construire `VEILLE_DATABASE_URL` comme dans `.env.example`
   (utilisateur `veille_app.<project-ref>`, `?ssl=require`). Vérifier le préfixe de l'hôte
   (`aws-0-…` ou `aws-1-…`) dans l'écran Connect : un mauvais cluster répond
   « Tenant or user not found ».

### 2. Backend sur Render (offre gratuite)

Service Docker décrit par `render.yaml` (Blueprint) : `rootDir: backend`, région Francfort,
secrets en `sync: false` (saisis dans le dashboard, jamais dans git) :
`VEILLE_DATABASE_URL`, `VEILLE_TOTP_ENCRYPTION_KEY`, `VEILLE_INTERNAL_TOKEN_SHA256`.

- **Migrations** : `alembic upgrade head` tourne dans le `CMD`, avant uvicorn. Acceptable
  tant qu'il n'y a qu'une instance (offre gratuite) ; le pre-deploy de Render est payant.
- **Endormissement** : le service s'arrête après 15 min sans trafic entrant. Le keep-alive
  est un workflow n8n (`GET /api/health` toutes les 10 min) : ~744 h/mois sur les 750 h
  gratuites du workspace, donc un seul service gratuit possible.
- **Premier admin** : `veille-admin create-admin --email …` depuis un poste qui atteint
  Supabase, avec `VEILLE_DATABASE_URL` pointée dessus.

### 3. Frontend sur Vercel

1. L'URL Render est dans `frontend/vercel.json` (règle `/api/:path*`).
2. Projet Vercel avec **Root Directory = `frontend`** ; le reste est lu depuis `vercel.json`
   (Node 24 via `engines`).

Le rewrite rend l'API **same-origin** : pas de CORS à ouvrir, cookies `SameSite=Strict`.

### 4. n8n

Workflow « Veille RSS → site (zero trust) » :
1. Nœud **Config** : `api_base` = URL Render directe (`https://veille-api-6wcq.onrender.com`) : un saut de moins, et pas de protection de déploiement Vercel sur le chemin.
2. Credential **Bearer** « Veille site - jeton n8n » = le jeton en clair.
3. Publier, puis dépublier l'ancien « Veille RSS (sources pilotées par Data Table) ».

## Développement local

```bash
docker compose up -d db
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
export VEILLE_DATABASE_URL=postgresql+asyncpg://veille:veille@127.0.0.1:5432/veille
export VEILLE_TOTP_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export VEILLE_INTERNAL_TOKEN_SHA256=$(printf dev | sha256sum | cut -d' ' -f1) VEILLE_COOKIE_SECURE=false
alembic upgrade head && veille-admin create-admin --email admin@local.test
uvicorn veille.main:app_factory --factory --port 8000

cd ../frontend && npm ci && npx ng serve   # proxy /api → :8000
```

Tests (sur un vrai Postgres, schéma issu des migrations) :
`VEILLE_TEST_DATABASE_URL=… pytest`
