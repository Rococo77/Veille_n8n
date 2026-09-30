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

_RESEND_URL = "https://api.resend.com/emails"
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


class ResendMailer:
    def __init__(self, settings: Settings) -> None:
        assert settings.mail_api_key is not None
        self._key = settings.mail_api_key.get_secret_value()
        self._sender = f"{settings.mail_from_name} <{settings.mail_from}>"
        self._reply_to = settings.mail_reply_to

    async def send(self, mail: Mail) -> bool:
        body: dict[str, object] = {
            "from": self._sender,
            "to": [mail.to],
            "subject": mail.subject,
            "text": mail.text,
        }
        if self._reply_to:
            body["reply_to"] = self._reply_to
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    _RESEND_URL,
                    json=body,
                    headers={"Authorization": f"Bearer {self._key}"},
                )
        except httpx.HTTPError as exc:
            logger.warning("envoi de mail impossible : %s", type(exc).__name__)
            return False
        if response.is_success:
            return True
        # Statut seul : le corps de la réponse peut reprendre la requête, donc le lien.
        logger.warning("envoi de mail refusé par Resend : HTTP %s", response.status_code)
        return False


def build_mailer(settings: Settings) -> Mailer:
    return ResendMailer(settings) if settings.mail_api_key else DisabledMailer()
