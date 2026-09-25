import pyotp
from sqlalchemy import select

from tests.conftest import PASSWORD, create_user, make_client
from veille.models import User


async def _pre_mfa_login(client, settings, email: str) -> None:  # type: ignore[no-untyped-def]
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies.get(settings.csrf_cookie_name)


async def test_login_requires_mfa_rotates_token_and_rejects_code_replay(app, anon, db, settings):
    await create_user(db, "alice@example.org", "viewer")

    # Email normalisé : la casse ne crée pas de doublon ni de contournement.
    await _pre_mfa_login(anon, settings, "Alice@Example.org")
    pre_token = anon.cookies.get(settings.session_cookie_name)

    r = await anon.get("/api/groups")
    assert r.status_code == 401
    assert r.json()["type"].endswith("mfa-required")

    secret = (await anon.post("/api/auth/mfa/enroll")).json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = await anon.post("/api/auth/mfa/verify", json={"code": code})
    assert r.status_code == 200, r.text

    full_token = anon.cookies.get(settings.session_cookie_name)
    assert full_token != pre_token
    anon.headers["X-CSRF-Token"] = anon.cookies.get(settings.csrf_cookie_name)
    assert (await anon.get("/api/groups")).status_code == 200

    async with make_client(app) as attacker:
        attacker.cookies.set(settings.session_cookie_name, pre_token)
        assert (await attacker.get("/api/auth/me")).status_code == 401

    # Le même code, rejoué dans la même fenêtre de 30 s, doit être refusé.
    assert (await anon.post("/api/auth/logout")).status_code == 204
    await _pre_mfa_login(anon, settings, "alice@example.org")
    r = await anon.post("/api/auth/mfa/verify", json={"code": code})
    assert r.status_code == 401
    assert r.json()["type"].endswith("mfa-invalid")


async def test_account_locks_after_five_failures_even_with_right_password(anon, db):
    await create_user(db, "bob@example.org", "viewer")
    for _ in range(5):
        r = await anon.post(
            "/api/auth/login", json={"email": "bob@example.org", "password": "wrong-password"}
        )
        assert r.status_code == 401
    r = await anon.post("/api/auth/login", json={"email": "bob@example.org", "password": PASSWORD})
    assert r.status_code == 401
    # Même message pour un compte inexistant : pas d'énumération.
    unknown = await anon.post(
        "/api/auth/login", json={"email": "nobody@example.org", "password": PASSWORD}
    )
    assert unknown.json()["detail"] == r.json()["detail"]

    db.expire_all()
    user = await db.scalar(select(User).where(User.email == "bob@example.org"))
    assert user is not None and user.locked_until is not None


async def test_mfa_brute_force_kills_pre_session(anon, db, settings):
    await create_user(db, "carol@example.org", "viewer")
    await _pre_mfa_login(anon, settings, "carol@example.org")
    await anon.post("/api/auth/mfa/enroll")
    statuses = [
        (await anon.post("/api/auth/mfa/verify", json={"code": "000000"})).status_code
        for _ in range(5)
    ]
    assert statuses == [401] * 5
    # La session pré-MFA est détruite : il faut repasser par le mot de passe.
    r = await anon.post("/api/auth/mfa/verify", json={"code": "000000"})
    assert r.json()["type"].endswith("unauthenticated")


async def test_unsafe_request_without_csrf_or_with_form_encoding_is_refused(login_as):
    editor = await login_as("editor")
    payload = {"name": "Sécurité", "color": "#aa0000"}

    csrf = editor.client.headers.pop("X-CSRF-Token")
    r = await editor.client.post("/api/themes", json=payload)
    assert r.status_code == 403 and r.json()["type"].endswith("csrf")

    editor.client.headers["X-CSRF-Token"] = "forged"
    assert (await editor.client.post("/api/themes", json=payload)).status_code == 403

    editor.client.headers["X-CSRF-Token"] = csrf
    r = await editor.client.post("/api/themes", data=payload)
    assert r.status_code == 415

    assert (await editor.client.post("/api/themes", json=payload)).status_code == 201


async def test_roles_are_enforced_on_every_endpoint(login_as):
    viewer = await login_as("viewer")
    editor = await login_as("editor")

    assert (await viewer.client.post("/api/themes", json={"name": "X"})).status_code == 403
    assert (await editor.client.get("/api/users")).status_code == 403
    assert (await editor.client.get("/api/audit")).status_code == 403
    assert (await viewer.client.get("/api/articles")).status_code == 200


async def test_disabling_user_revokes_live_sessions_and_admin_cannot_edit_self(login_as):
    admin = await login_as("admin")
    viewer = await login_as("viewer")
    assert (await viewer.client.get("/api/auth/me")).status_code == 200

    r = await admin.client.patch(f"/api/users/{viewer.user.id}", json={"is_active": False})
    assert r.status_code == 200
    assert (await viewer.client.get("/api/auth/me")).status_code == 401

    r = await admin.client.patch(f"/api/users/{admin.user.id}", json={"role": "viewer"})
    assert r.status_code == 409


async def test_validation_errors_never_echo_submitted_values(anon):
    r = await anon.post("/api/auth/login", json={"email": "x", "password": "s3cr3t-value"})
    assert r.status_code == 422
    assert "s3cr3t-value" not in r.text
