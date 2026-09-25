import pytest

from tests.conftest import Actor


async def seed_group(
    editor: Actor,
    *,
    name: str = "Veille techno",
    veille_type: str = "technologique",
    theme: str = "Dev",
) -> tuple[str, str]:
    theme_r = await editor.client.post("/api/themes", json={"name": theme, "color": "#123456"})
    assert theme_r.status_code == 201, theme_r.text
    group_r = await editor.client.post(
        "/api/groups",
        json={"name": name, "veille_type": veille_type, "theme_id": theme_r.json()["id"]},
    )
    assert group_r.status_code == 201, group_r.text
    return theme_r.json()["id"], group_r.json()["id"]


async def test_group_with_sources_and_counts(login_as):
    editor = await login_as("editor")
    _, group_id = await seed_group(editor)

    r = await editor.client.post(
        f"/api/groups/{group_id}/sources",
        json={"name": "Flux", "url": "HTTPS://Feeds.Example.org/rss?x=1#frag"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["url"] == "https://feeds.example.org/rss?x=1"

    dup = await editor.client.post(
        f"/api/groups/{group_id}/sources",
        json={"name": "Doublon", "url": "https://feeds.example.org/rss?x=1"},
    )
    assert dup.status_code == 409

    groups = (await editor.client.get("/api/groups?veille_type=technologique")).json()
    assert [(g["name"], g["source_count"]) for g in groups] == [("Veille techno", 1)]
    assert (await editor.client.get("/api/groups?veille_type=securite")).json() == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/feed",
        "http://localhost/feed",
        "http://metadata.internal/latest",
        "http://169.254.169.254/latest/meta-data",
        "http://[::ffff:10.0.0.1]/rss",
        "http://internal.example.org/rss",
        "http://rebind.example.org/rss",
        "https://feeds.example.org:8443/rss",
        "http://user:pw@feeds.example.org/rss",
        "ftp://feeds.example.org/rss",
        "javascript:alert(1)//feeds.example.org",
        "http://unknown.example.org/rss",
    ],
)
async def test_source_urls_that_would_turn_n8n_into_an_ssrf_relay_are_refused(login_as, url):
    editor = await login_as("editor")
    _, group_id = await seed_group(editor)
    r = await editor.client.post(f"/api/groups/{group_id}/sources", json={"name": "x", "url": url})
    assert r.status_code == 422, r.text


async def test_theme_in_use_cannot_be_deleted_and_group_delete_cascades(login_as):
    editor = await login_as("editor")
    theme_id, group_id = await seed_group(editor)
    await editor.client.post(
        f"/api/groups/{group_id}/sources",
        json={"name": "Flux", "url": "https://feeds.example.org/rss"},
    )

    r = await editor.client.delete(f"/api/themes/{theme_id}")
    assert r.status_code == 409

    assert (await editor.client.delete(f"/api/groups/{group_id}")).status_code == 204
    assert (await editor.client.delete(f"/api/themes/{theme_id}")).status_code == 204


async def test_patch_with_explicit_null_does_not_break_not_null_columns(login_as):
    editor = await login_as("editor")
    _, group_id = await seed_group(editor)
    r = await editor.client.patch(
        f"/api/groups/{group_id}", json={"theme_id": None, "enabled": False}
    )
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False
