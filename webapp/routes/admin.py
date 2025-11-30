from fastapi import APIRouter, Depends
from ..security.rbac import require_role

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/reload-cache")
def reload_cache(user = Depends(require_role("admin", "developer"))):
    return {"status": "cache reloaded"}
