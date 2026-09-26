import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from typing import TypeVar

import anyio
import anyio.to_thread
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()
# Hash factice : on paie le coût argon2 même quand l'email n'existe pas, sinon le temps de
# réponse révèle quels comptes existent.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

TOTP_PERIOD = 30

# argon2 (profil par défaut : 64 Mio, t=3, p=4) sur l'offre Render à 512 Mo : au-delà de
# deux calculs simultanés, un afflux de logins suffit à faire tuer le conteneur (OOM).
# Le calcul part dans un thread : exécuté dans la boucle, il gèlerait toutes les requêtes.
_ARGON2_SLOTS = anyio.CapacityLimiter(2)
# Borne l'attente : chaque login en file garde une requête ouverte ; mieux vaut un 503
# immédiat qu'une file illimitée.
_ARGON2_QUEUE_TIMEOUT_S = 5.0


class HasherBusyError(RuntimeError):
    """Tous les créneaux argon2 sont occupés au-delà du délai d'attente."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


T = TypeVar("T")


async def _run_argon2(fn: Callable[[], T]) -> T:
    try:
        with anyio.fail_after(_ARGON2_QUEUE_TIMEOUT_S):
            await _ARGON2_SLOTS.acquire()
    except TimeoutError as exc:
        raise HasherBusyError from exc
    try:
        return await anyio.to_thread.run_sync(fn)
    finally:
        _ARGON2_SLOTS.release()


async def verify_password_async(password_hash: str | None, password: str) -> bool:
    return await _run_argon2(lambda: verify_password(password_hash, password))


async def hash_password_async(password: str) -> str:
    return await _run_argon2(lambda: hash_password(password))


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def constant_time_equals(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


class TotpCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("secret TOTP illisible (clé de chiffrement changée ?)") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def match_totp_step(
    secret: str, code: str, last_step: int | None, now: float | None = None
) -> int | None:
    """Renvoie le pas de temps validé, ou None.

    pyotp.verify() ne dit pas quel pas a matché : impossible alors d'interdire le rejeu
    d'un code déjà utilisé dans la même fenêtre. On compare donc pas par pas.
    """
    totp = pyotp.TOTP(secret)
    current = int((now if now is not None else time.time()) // TOTP_PERIOD)
    for step in (current - 1, current, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.at(step * TOTP_PERIOD), code):
            return step
    return None
