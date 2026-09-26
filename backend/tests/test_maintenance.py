from datetime import timedelta

from sqlalchemy import select, text

from tests.conftest import service_headers
from tests.test_catalog import seed_group
from tests.test_ingest import _source
from veille.db import utcnow
from veille.models import AuditEvent


async def test_purge_honours_server_retention_and_is_audited(anon, login_as, db, settings):
    editor = await login_as("editor")
    _, group_id = await seed_group(editor)
    source_id = await _source(editor, group_id)
    payload = {
        "source_id": source_id,
        "ok": True,
        "articles": [
            {"link": "https://a.example/old", "title": "Ancien"},
            {"link": "https://a.example/new", "title": "Récent"},
        ],
    }
    r = await anon.post("/api/internal/ingest", json=payload, headers=service_headers())
    assert r.json()["inserted"] == 2

    old = utcnow() - timedelta(days=settings.article_retention_days + 1)
    await db.execute(
        text("UPDATE articles SET fetched_at = :t WHERE link = :l"),
        {"t": old, "l": "https://a.example/old"},
    )
    await db.execute(
        text("UPDATE audit_events SET at = :t"),
        {"t": utcnow() - timedelta(days=settings.audit_retention_days + 1)},
    )
    await db.commit()

    # Surface machine uniquement : une session admin n'y a pas accès.
    admin = await login_as("admin")
    assert (await admin.client.post("/api/internal/purge")).status_code == 401

    r = await anon.post("/api/internal/purge", headers=service_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["articles"] == 1 and body["audit_events"] >= 1

    links = [a["link"] for a in (await editor.client.get("/api/articles")).json()["items"]]
    assert links == ["https://a.example/new"]
    db.expire_all()
    actions = (await db.scalars(select(AuditEvent.action))).all()
    assert actions == ["maintenance.purge"]
