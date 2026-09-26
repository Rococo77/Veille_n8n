from fastapi import APIRouter, Depends

from veille.db import utcnow
from veille.deps import AppSettings, ClientIp, Db, require_service
from veille.schemas import IngestIn, IngestOut, InternalSourceOut, PurgeOut
from veille.services import ingest, maintenance

# Surface réservée à n8n : aucune session utilisateur n'y donne accès, et le jeton de
# service ne donne accès à rien d'autre.
router = APIRouter(
    prefix="/api/internal", tags=["internal"], dependencies=[Depends(require_service)]
)


@router.get("/sources", response_model=list[InternalSourceOut])
async def list_sources(db: Db) -> list[InternalSourceOut]:
    return await ingest.enabled_sources(db)


@router.post("/ingest", response_model=IngestOut)
async def ingest_results(payload: IngestIn, db: Db, ip: ClientIp) -> IngestOut:
    return await ingest.ingest(db, payload, ip=ip, now=utcnow())


@router.post("/purge", response_model=PurgeOut)
async def purge(db: Db, settings: AppSettings, ip: ClientIp) -> PurgeOut:
    return await maintenance.purge(db, settings, ip=ip, now=utcnow())
