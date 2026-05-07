"""API key tabanlı kimlik doğrulama."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings


security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """API key'i doğrula. Geçersiz ise 401 fırlat.

    Returns: Geçerli API key
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header eksik. 'Bearer <api_key>' kullanın.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    valid_keys = settings.get_api_keys()
    if credentials.credentials not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
