import re
from datetime import timedelta

from sqlalchemy import select, text

from tests.conftest import make_client
from veille.db import utcnow
from veille.models import AuditEvent, Invitation

NEW_PASSWORD = "une phrase de passe assez longue"


def _token(url: str) -> str:
    # Le jeton est dans le fragment : il n'atteint jamais un serveur via l'URL.
    match = re.search(r"/invitation#([A-Za-z0-9_-]+)$", url)
    assert match, url
    return match.group(1)


def _mail_token(mail) -> str:  # type: ignore[no-untyped-def]
    return _token(next(line for line in mail.text.splitlines() if "/invitation#" in line))


async def test_invitation_flow_single_use_and_leads_to_mfa(app, login_as, mailer, db, settings):
    admin = await login_as("admin")
    r = await admin.client.post("/api/users", json={"email": "Eve@Example.org", "role": "editor"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mail_sent"] is True and body["invitation_url"] is None
    assert body["user"]["has_password"] is False

    [mail] = mailer.sent
    assert mail.to == "eve@example.org"
    token = _mail_token(mail)
    # Seul le hash est stocké.
    stored = (await db.scalars(select(Invitation.token_hash))).one()
    assert token.encode() not in stored

    async with make_client(app) as guest:
        # Sans mot de passe, le compte invité ne peut pas se connecter.
        r = await guest.post(
            "/api/auth/login", json={"email": "eve@example.org", "password": NEW_PASSWORD}
        )
        assert r.status_code == 401

        info = await guest.post("/api/invitations/lookup", json={"token": token})
        assert info.json()["email"] == "eve@example.org" and info.json()["role"] == "editor"

        r = await guest.post(
            "/api/invitations/accept", json={"token": token, "password": NEW_PASSWORD}
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"mfa_enrolled": False}
        # Session pré-MFA : le fil reste fermé tant que le second facteur n'est pas configuré.
        assert guest.cookies.get(settings.session_cookie_name)
        guest.headers["X-CSRF-Token"] = guest.cookies.get(settings.csrf_cookie_name)
        assert (await guest.get("/api/groups")).json()["type"].endswith("mfa-required")

        replay = await guest.post(
            "/api/invitations/accept", json={"token": token, "password": NEW_PASSWORD}
        )
        assert replay.status_code == 404

        r = await guest.post(
            "/api/auth/login", json={"email": "eve@example.org", "password": NEW_PASSWORD}
        )
        assert r.status_code == 200


async def test_reissue_revokes_previous_link_and_expired_links_fail(anon, login_as, mailer, db):
    admin = await login_as("admin")
    r = await admin.client.post("/api/users", json={"email": "finn@example.org"})
    first = _mail_token(mailer.sent[-1])
    user_id = r.json()["user"]["id"]

    r = await admin.client.post(f"/api/users/{user_id}/invitation")
    assert r.status_code == 200, r.text
    second = _mail_token(mailer.sent[-1])

    assert (await anon.post("/api/invitations/lookup", json={"token": first})).status_code == 404
    assert (await anon.post("/api/invitations/lookup", json={"token": second})).status_code == 200

    await db.execute(
        text("UPDATE invitations SET expires_at = :t, created_at = :c"),
        {"t": utcnow() - timedelta(minutes=1), "c": utcnow() - timedelta(hours=2)},
    )
    await db.commit()
    r = await anon.post("/api/invitations/accept", json={"token": second, "password": NEW_PASSWORD})
    assert r.status_code == 404


async def test_link_is_returned_to_admin_only_when_mail_did_not_leave(login_as, mailer, db):
    admin = await login_as("admin")
    mailer.accept = False
    r = await admin.client.post("/api/users", json={"email": "gus@example.org"})
    assert r.status_code == 201
    body = r.json()
    assert body["mail_sent"] is False
    assert _token(body["invitation_url"])

    db.expire_all()
    actions = set((await db.scalars(select(AuditEvent.action))).all())
    assert {"user.invited", "invitation.mail_not_sent"} <= actions
