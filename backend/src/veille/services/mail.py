"""Envoi de mails transactionnels.

Le contenu d'un mail d'invitation contient un lien secret : il n'est jamais journalisé,
ni en cas de succès, ni en cas d'échec.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from veille.config import Settings

logger = logging.getLogger("veille.mail")

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = httpx.Timeout(10.0)


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str


class Mailer(Protocol):
    async def send(self, mail: Mail) -> bool:
        """Renvoie False si le mail n'est pas parti ; ne lève jamais."""
        ...


class DisabledMailer:
    """Aucune clé configurée : rien ne part, l'appelant bascule sur le lien manuel."""

    async def send(self, mail: Mail) -> bool:
        logger.info("envoi de mail désactivé (VEILLE_MAIL_API_KEY absente)")
        return False


class BrevoMailer:
    def __init__(self, settings: Settings) -> None:
        assert settings.mail_api_key is not None
        self._key = settings.mail_api_key.get_secret_value()
        self._sender = {"email": settings.mail_from, "name": settings.mail_from_name}
        self._reply_to = {"email": settings.mail_reply_to} if settings.mail_reply_to else None

    async def send(self, mail: Mail) -> bool:
        body: dict[str, object] = {
            "sender": self._sender,
            "to": [{"email": mail.to}],
            "subject": mail.subject,
            "textContent": mail.text,
        }
        if self._reply_to:
            body["replyTo"] = self._reply_to
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    _BREVO_URL,
                    json=body,
                    headers={"api-key": self._key, "accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            logger.warning("envoi de mail impossible : %s", type(exc).__name__)
            return False
        if response.is_success:
            return True
        # Statut seul : le corps de la réponse peut reprendre la requête, donc le lien.
        logger.warning("envoi de mail refusé par Brevo : HTTP %s", response.status_code)
        return False


def build_mailer(settings: Settings) -> Mailer:
    return BrevoMailer(settings) if settings.mail_api_key else DisabledMailer()
