from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


def _configured_roles() -> dict[str, str]:
    return {
        role: token
        for role, token in (
            ("admin", settings.admin_api_token),
            ("placement_manager", settings.placement_api_token),
            ("auditor", settings.auditor_api_token),
        )
        if token
    }


def require_roles(*roles: str) -> Callable:
    allowed = frozenset(roles)

    def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        if not settings.auth_enabled:
            return "development"
        configured = _configured_roles()
        if not configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is enabled but no role API tokens are configured",
            )
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
        role = next(
            (name for name, token in configured.items() if secrets.compare_digest(credentials.credentials, token)),
            None,
        )
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return role

    return authorize
