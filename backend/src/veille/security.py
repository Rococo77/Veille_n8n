import hashlib
import hmac
import secrets
import time

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()
# Hash factice : on paie le coût argon2 même quand l'email n'existe pas, sinon le temps de
# réponse révèle quels comptes existent.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

TOTP_PERIOD = 30


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


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
