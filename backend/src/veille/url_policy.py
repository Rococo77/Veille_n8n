"""Politique d'URL des sources.

Le site ne télécharge jamais les flux, mais n8n si : une source pointant vers
http://169.254.169.254/ ou un service interne du VPS ferait de n8n un relais SSRF,
et le contenu récupéré finirait affiché dans le site. On refuse donc tout ce qui ne
résout pas vers une adresse publique.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from veille.errors import DomainError

Resolver = Callable[[str], Awaitable[list[str]]]

_FORBIDDEN_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home.arpa")
_DNS_TIMEOUT_S = 3.0


async def system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(host, None, type=socket.SOCK_STREAM), timeout=_DNS_TIMEOUT_S
    )
    return sorted({info[4][0] for info in infos})


def _invalid(detail: str) -> DomainError:
    return DomainError(422, "URL de source refusée", detail, "invalid-source-url")


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def normalize_source_url(raw: str, resolver: Resolver) -> str:
    parts = urlsplit(raw.strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise _invalid("Seuls les schémas http et https sont acceptés.")
    if parts.username or parts.password:
        raise _invalid("Les identifiants dans l'URL sont interdits.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise _invalid("Nom d'hôte manquant.")
    try:
        port = parts.port
    except ValueError as exc:
        raise _invalid("Port invalide.") from exc
    if port not in (None, 80, 443):
        raise _invalid("Seuls les ports 80 et 443 sont acceptés.")
    if host == "localhost" or host.endswith(_FORBIDDEN_SUFFIXES):
        raise _invalid("Les hôtes locaux sont interdits.")

    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None

    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            host.encode("idna")
            addresses = await resolver(host)
        except (UnicodeError, OSError, TimeoutError) as exc:
            raise _invalid("Nom d'hôte introuvable.") from exc
    if not addresses or not all(_is_public(a) for a in addresses):
        raise _invalid("L'hôte doit résoudre uniquement vers des adresses publiques.")

    netloc = parts.netloc.rsplit("@", 1)[-1].lower()
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))
