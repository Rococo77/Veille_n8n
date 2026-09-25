from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VEILLE_", env_file=".env", extra="ignore")

    database_url: str = Field(description="postgresql+asyncpg://user:pass@host:5432/db")
    # Le pooler de session Supabase (offre gratuite) plafonne les connexions simultanées :
    # un petit pool par instance, et un nombre d'instances borné côté hébergeur.
    database_pool_size: int = Field(default=3, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    # Clé Fernet : une fuite de la base seule ne doit pas exposer les secrets TOTP.
    totp_encryption_key: SecretStr
    # Seul le hash du token n8n vit côté site : le token en clair n'existe que dans n8n.
    internal_token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    cookie_secure: bool = True
    session_idle_minutes: int = Field(default=30, ge=5, le=240)
    session_absolute_hours: int = Field(default=12, ge=1, le=72)
    pre_mfa_minutes: int = Field(default=5, ge=1, le=15)
    totp_issuer: str = "Veille"
    enable_docs: bool = False

    @property
    def session_cookie_name(self) -> str:
        # Le préfixe __Host- impose Secure + Path=/ + pas de Domain : impossible à poser
        # depuis un sous-domaine compromis.
        return "__Host-veille_session" if self.cookie_secure else "veille_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-veille_csrf" if self.cookie_secure else "veille_csrf"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
