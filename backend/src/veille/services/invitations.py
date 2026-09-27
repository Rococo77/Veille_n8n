"""Invitations : l'admin ouvre un compte, l'utilisateur choisit lui-même son mot de passe.

Le jeton n'existe en clair que dans le lien envoyé ; la base n'en garde que le SHA-256.
Il sert une seule fois, expire, et en émettre un nouveau révoque le précédent.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from veille.config import Settings
from veille.errors import DomainError, conflict, constraint_name, not_found
from veille.models import Invitation, User
from veille.schemas import (
    InvitationAcceptIn,
    InvitationInfoOut,
    InvitationOut,
    UserInviteIn,
    UserOut,
)
from veille.security import hash_password_async, new_token, sha256
from veille.services import audit, sessions
from veille.services.mail import Mail, Mailer
from veille.services.sessions import IssuedSession

_ROLE_LABELS = {"viewer": "Lecture", "editor": "Édition", "admin": "Administration"}


# Même réponse pour un jeton inconnu, expiré ou déjà utilisé : rien à apprendre en sondant.
def _invalid() -> DomainError:
    return DomainError(
        404, "Invitation invalide", "Ce lien est invalide, expiré ou déjà utilisé.", "invitation"
    )


@dataclass(frozen=True)
class _Issued:
    token: str
    expires_at: datetime


def _issue(
    db: AsyncSession, user: User, actor: User | None, settings: Settings, now: datetime
) -> _Issued:
    token = new_token()
    expires_at = now + timedelta(hours=settings.invitation_hours)
    db.add(
        Invitation(
            token_hash=sha256(token),
            user_id=user.id,
            created_by=actor.id if actor else None,
            created_at=now,
            expires_at=expires_at,
        )
    )
    return _Issued(token, expires_at)


def _link(settings: Settings, token: str) -> str:
    return f"{settings.public_base_url}/invitation#{token}"


def _mail(user: User, actor: User | None, link: str, settings: Settings) -> Mail:
    inviter = actor.email if actor else "Un administrateur"
    return Mail(
        to=user.email,
        subject="Votre accès à Veille (ByteNorth)",
        text=(
            "Bonjour,\n\n"
            f"{inviter} vous a ouvert un compte sur Veille, l'outil de veille de ByteNorth.\n\n"
            f"Identifiant : {user.email}\n"
            f"Rôle : {_ROLE_LABELS.get(user.role, user.role)}\n\n"
            "Pour activer votre compte, ouvrez ce lien personnel :\n"
            f"{link}\n\n"
            f"Il est valable {settings.invitation_hours} heures et ne fonctionne qu'une fois.\n"
            "Vous choisirez votre mot de passe (12 caractères minimum), puis configurerez une\n"
            "application d'authentification (Google Authenticator, Aegis, 1Password...) :\n"
            "le second facteur est obligatoire.\n\n"
            "Ne transférez pas ce message. Si vous n'attendiez pas cette invitation,\n"
            "ignorez-le : sans activation, le compte reste inutilisable.\n"
        ),
    )


async def _deliver(
    db: AsyncSession,
    user: User,
    actor: User | None,
    issued: _Issued,
    settings: Settings,
    mailer: Mailer,
    ip: str | None,
) -> InvitationOut:
    # Envoyé après le commit : un fournisseur de mail lent ne tient pas de transaction ouverte,
    # et un échec d'envoi n'annule pas la création du compte.
    link = _link(settings, issued.token)
    sent = await mailer.send(_mail(user, actor, link, settings))
    if not sent:
        audit.record(db, action="invitation.mail_not_sent", actor=actor, target=str(user.id), ip=ip)
        await db.commit()
    return InvitationOut(
        user=UserOut.model_validate(user),
        mail_sent=sent,
        expires_at=issued.expires_at,
        invitation_url=None if sent else link,
    )


async def invite_user(
    db: AsyncSession,
    data: UserInviteIn,
    actor: User,
    settings: Settings,
    mailer: Mailer,
    *,
    ip: str | None,
    now: datetime,
) -> InvitationOut:
    user = User(email=data.email, password_hash=None, role=data.role)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if constraint_name(exc) == "uq_users_email":
            raise conflict("Un compte existe déjà avec cet email.") from exc
        raise
    issued = _issue(db, user, actor, settings, now)
    audit.record(
        db,
        action="user.invited",
        actor=actor,
        target=str(user.id),
        ip=ip,
        details={"role": data.role},
    )
    await db.commit()
    await db.refresh(user)
    return await _deliver(db, user, actor, issued, settings, mailer, ip)


async def reinvite(
    db: AsyncSession,
    user_id: uuid.UUID,
    actor: User,
    settings: Settings,
    mailer: Mailer,
    *,
    ip: str | None,
    now: datetime,
) -> InvitationOut:
    if user_id == actor.id:
        raise DomainError(409, "Conflit", "Changez votre mot de passe depuis votre compte.", "self")
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("Utilisateur")
    if not user.is_active:
        raise conflict("Réactivez le compte avant de lui envoyer un lien.")
    # Un seul lien vivant : l'ancien, peut-être intercepté, cesse de fonctionner.
    await db.execute(delete(Invitation).where(Invitation.user_id == user.id))
    issued = _issue(db, user, actor, settings, now)
    audit.record(
        db,
        action="invitation.reissued",
        actor=actor,
        target=str(user.id),
        ip=ip,
        details={"had_password": user.has_password},
    )
    await db.commit()
    return await _deliver(db, user, actor, issued, settings, mailer, ip)


async def _valid(
    db: AsyncSession, token: str, now: datetime, *, lock: bool = False
) -> tuple[Invitation, User]:
    stmt = (
        select(Invitation, User)
        .join(User, Invitation.user_id == User.id)
        .where(Invitation.token_hash == sha256(token))
    )
    if lock:
        # Deux validations simultanées du même lien : la seconde attend puis ne trouve plus rien.
        stmt = stmt.with_for_update(of=Invitation)
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise _invalid()
    invitation, user = row
    if invitation.expires_at <= now or not user.is_active:
        raise _invalid()
    return invitation, user


async def lookup(db: AsyncSession, token: str, now: datetime) -> InvitationInfoOut:
    invitation, user = await _valid(db, token, now)
    return InvitationInfoOut(
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        expires_at=invitation.expires_at,
    )


async def accept(
    db: AsyncSession,
    data: InvitationAcceptIn,
    settings: Settings,
    *,
    ip: str | None,
    user_agent: str | None,
    now: datetime,
) -> tuple[IssuedSession, User]:
    # Le jeton est vérifié avant argon2 : sans lien valide, pas de calcul coûteux à provoquer.
    invitation, user = await _valid(db, data.token, now, lock=True)
    if data.password.lower() == user.email:
        raise DomainError(422, "Mot de passe refusé", "Identique à l'email.", "weak-password")
    user.password_hash = await hash_password_async(data.password)
    user.failed_logins = 0
    user.locked_until = None
    await db.delete(invitation)
    # Lien utilisé pour réinitialiser un mot de passe : les sessions existantes tombent.
    await sessions.revoke_all(db, user.id)
    issued = sessions.issue(
        db, user, mfa_verified=False, settings=settings, ip=ip, user_agent=user_agent, now=now
    )
    audit.record(db, action="invitation.accepted", actor=user, target=str(user.id), ip=ip)
    await db.commit()
    return issued, user
