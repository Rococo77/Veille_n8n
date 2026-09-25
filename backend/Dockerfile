# syntax=docker/dockerfile:1

FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN python -m venv /venv
# Dépendances figées d'abord : couche mise en cache tant que le lock ne change pas.
COPY requirements.lock ./
RUN /venv/bin/pip install -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
RUN /venv/bin/pip install --no-deps .

FROM python:3.12-slim
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin veille
WORKDIR /app
COPY --from=build /venv /venv
COPY alembic.ini ./
COPY alembic ./alembic
USER 10001
EXPOSE 8080
# Cloud Run injecte PORT. Les migrations ne tournent PAS au démarrage : plusieurs instances
# à froid lanceraient Alembic en parallèle. Elles passent par un job dédié (voir README).
# Derrière Cloud Run + Vercel, request.client.host n'est qu'informatif (journal d'audit) :
# aucune décision de sécurité ne repose sur l'IP.
CMD ["sh", "-c", "exec uvicorn veille.main:app_factory --factory --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
