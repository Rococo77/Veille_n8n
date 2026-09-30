import json

import httpx
import pytest
from pydantic import SecretStr

from veille.config import Settings
from veille.services import mail
from veille.services.mail import Mail, ResendMailer


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real = httpx.AsyncClient
    monkeypatch.setattr(
        mail.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


async def test_resend_request_shape(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "x"})

    _patch_client(monkeypatch, handler)
    cfg = settings.model_copy(
        update={"mail_api_key": SecretStr("re_test"), "mail_reply_to": "r@b.fr"}
    )

    sent = await ResendMailer(cfg).send(Mail(to="a@b.fr", subject="S", text="T"))

    assert sent is True
    (request,) = seen
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["authorization"] == "Bearer re_test"
    body = json.loads(request.content)
    assert body == {
        "from": f"{cfg.mail_from_name} <{cfg.mail_from}>",
        "to": ["a@b.fr"],
        "subject": "S",
        "text": "T",
        "reply_to": "r@b.fr",
    }


async def test_resend_refusal_returns_false(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_client(monkeypatch, lambda request: httpx.Response(403))
    cfg = settings.model_copy(update={"mail_api_key": SecretStr("re_test")})

    assert await ResendMailer(cfg).send(Mail(to="a@b.fr", subject="S", text="T")) is False
