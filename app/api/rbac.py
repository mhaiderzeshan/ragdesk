from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.auth import UserContext


def require_role(*allowed_roles: str):
    """
    Returns a FastAPI dependency that ensures the current user has one of the
    specified roles. Raises HTTP 403 if the role check fails.
    """
    async def _dependency(
        current_user: UserContext = Depends(get_current_user),
    ) -> UserContext:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires role: {' or '.join(allowed_roles)}",
            )
        return current_user

    return _dependency
