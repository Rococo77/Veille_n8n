from datetime import UTC, datetime, timedelta

from tests.conftest import SERVICE_TOKEN, service_headers
from tests.test_catalog import seed_group


async def _source(editor, group_id: str, url: str = "https://feeds.example.org/rss") -> str:  # type: ignore[no-untyped-def]
    r = await editor.client.post(
        f"/api/groups/{group_id}/sources", json={"name": "Flux", "url": url}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_internal_api_accepts_only_the_service_token(anon, login_as):
    admin = await login_as("admin")
    assert (await anon.get("/api/internal/sources")).status_code == 401
    assert (
        await anon.get("/api/internal/sources", headers=service_headers("nope"))
    ).status_code == 401
    # Une session admin ne donne aucun droit sur la surface machine.
    assert (await admin.client.get("/api/internal/sources")).status_code == 401
    assert (await anon.get("/api/internal/sources", headers=service_headers())).status_code == 200


async def test_internal_auth_is_checked_before_the_body_is_parsed(anon):
    r = await anon.post("/api/internal/ingest", json={"garbage": True})
    assert r.status_code == 401


async def test_only_enabled_sources_of_enabled_groups_are_exposed(anon, login_as):
    editor = await login_as("editor")
    _, g1 = await seed_group(editor)
    _, g2 = await seed_group(
        editor, name="Concurrence", veille_type="concurrentielle", theme="Marché"
    )
    s_on = await _source(editor, g1)
    s_off = await _source(editor, g1, "https://feeds.example.org/off")
    await editor.client.patch(f"/api/sources/{s_off}", json={"enabled": False})
    await _source(editor, g2)
    await editor.client.patch(f"/api/groups/{g2}", json={"enabled": False})

    r = await anon.get(
        "/api/internal/sources", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"}
    )
    assert [s["id"] for s in r.json()] == [s_on]


async def test_ingest_is_idempotent_and_sanitizes_untrusted_feed_content(anon, login_as):
    editor = await login_as("editor")
    _, group_id = await seed_group(editor)
    source_id = await _source(editor, group_id)
    future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    payload = {
        "source_id": source_id,
        "ok": True,
        "articles": [
            {
                "link": "https://a.example/1",
                "title": "<b>Titre</b> &amp; <script>x</script>",
                "published_at": "Wed, 24 Sep 2026 10:00:00 GMT",
            },
            {"link": "https://a.example/1", "title": "doublon dans le lot"},
            {"link": "javascript:alert(document.cookie)", "title": "piège"},
            {"link": "https://a.example/future", "title": "Futur", "published_at": future},
            {"title": "sans lien"},
        ],
    }

    first = await anon.post("/api/internal/ingest", json=payload, headers=service_headers())
    assert first.status_code == 200, first.text
    assert first.json() == {"inserted": 2, "rejected": 2}

    replay = await anon.post("/api/internal/ingest", json=payload, headers=service_headers())
    assert replay.json() == {"inserted": 0, "rejected": 2}

    items = (await editor.client.get("/api/articles")).json()["items"]
    by_link = {a["link"]: a for a in items}
    assert set(by_link) == {"https://a.example/1", "https://a.example/future"}
    assert by_link["https://a.example/1"]["title"] == "Titre & x"
    future_article = datetime.fromisoformat(by_link["https://a.example/future"]["published_at"])
    assert future_article <= datetime.now(UTC) + timedelta(minutes=1)


async def test_failed_fetch_is_recorded_on_the_source(anon, login_as):
    editor = await login_as("editor")
    _, group_id = await seed_group(editor)
    source_id = await _source(editor, group_id)
    for _ in range(2):
        await anon.post(
            "/api/internal/ingest",
            json={"source_id": source_id, "ok": False, "error": "<h1>502</h1> Bad Gateway"},
            headers=service_headers(),
        )
    detail = (await editor.client.get(f"/api/groups/{group_id}")).json()
    assert detail["failing_source_count"] == 1
    src = detail["sources"][0]
    assert (src["last_status"], src["consecutive_failures"], src["last_error"]) == (
        "error",
        2,
        "502 Bad Gateway",
    )


async def test_articles_filter_by_type_and_theme_with_stable_cursor_pagination(anon, login_as):
    editor = await login_as("editor")
    theme_dev, g_dev = await seed_group(editor)
    _, g_sec = await seed_group(editor, name="Alertes", veille_type="securite", theme="Cyber")
    s_dev = await _source(editor, g_dev)
    s_sec = await _source(editor, g_sec)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    for source_id, prefix in ((s_dev, "dev"), (s_sec, "sec")):
        articles = [
            {
                "link": f"https://a.example/{prefix}/{i}",
                "title": f"{prefix} {i}",
                "published_at": (base + timedelta(hours=i)).isoformat(),
            }
            for i in range(5)
        ]
        await anon.post(
            "/api/internal/ingest",
            json={"source_id": source_id, "ok": True, "articles": articles},
            headers=service_headers(),
        )

    sec = (await editor.client.get("/api/articles?veille_type=securite")).json()["items"]
    assert {a["group"]["veille_type"] for a in sec} == {"securite"} and len(sec) == 5

    seen: list[str] = []
    cursor = None
    while True:
        params = {"theme_id": theme_dev, "limit": 2, **({"cursor": cursor} if cursor else {})}
        page = (await editor.client.get("/api/articles", params=params)).json()
        seen += [a["title"] for a in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["dev 4", "dev 3", "dev 2", "dev 1", "dev 0"]

    assert (await editor.client.get("/api/articles?cursor=%%%")).status_code == 422
    # Les jokers LIKE saisis par l'utilisateur sont traités comme du texte.
    assert (await editor.client.get("/api/articles?q=%25%25")).json()["items"] == []
