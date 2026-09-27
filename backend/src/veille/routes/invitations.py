from fastapi import APIRouter, Request, Response

from veille.db import utcnow
from veille.deps import AppSettings, ClientIp, Db
from veille.routes.auth import set_session_cookies
from veille.schemas import InvitationAcceptIn, InvitationInfoOut, InvitationLookupIn, LoginOut
from veille.services import invitations

# Surface publique : le jeton d'invitation est la seule autorisation. Il voyage dans le
# corps JSON (jamais dans l'URL) pour ne laisser de trace dans aucun journal d'accès.
router = APIRouter(prefix="/api/invitations", tags=["invitations"])


@router.post("/lookup", response_model=InvitationInfoOut)
async def lookup(data: InvitationLookupIn, db: Db) -> InvitationInfoOut:
    return await invitations.lookup(db, data.token, utcnow())


@router.post("/accept", response_model=LoginOut)
async def accept(
    data: InvitationAcceptIn,
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    ip: ClientIp,
) -> LoginOut:
    issued, user = await invitations.accept(
        db, data, settings, ip=ip, user_agent=request.headers.get("user-agent"), now=utcnow()
    )
    # Session pré-MFA, comme après un login : l'étape suivante est le second facteur.
    set_session_cookies(response, settings, issued)
    return LoginOut(mfa_enrolled=user.totp_confirmed)
