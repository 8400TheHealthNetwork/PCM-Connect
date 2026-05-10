import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import get_settings

security = HTTPBasic()


def require_api_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    settings = get_settings()

    user_ok = secrets.compare_digest(credentials.username, settings.auth.username)
    pass_ok = secrets.compare_digest(credentials.password, settings.auth.password)

    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
