from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.deps import Ctx, get_ctx
from app.errors import AppError, not_found
from app.services.security import read_file_key
from app.storage import get_storage, guess_type

router = APIRouter(tags=["files"])


@router.get("/files/{key:path}")
def get_file(key: str, ctx: Ctx = Depends(get_ctx)) -> Response:
    if not key.startswith(f"c{ctx.client_id}/"):
        raise AppError(403, "client_forbidden")
    storage = get_storage()
    if not storage.exists(key):
        raise not_found()
    return Response(storage.read(key), media_type=guess_type(key), headers={"Cache-Control": "private, max-age=300"})


@router.get("/public/files/{token}")
def get_public_file(token: str) -> Response:
    """Signed, expiring links (ally packages)."""
    key = read_file_key(token)
    storage = get_storage()
    if not key or not storage.exists(key):
        raise not_found()
    return Response(storage.read(key), media_type=guess_type(key))
