from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
from database import get_db

SessionDep = Annotated[Session, Depends(get_db)]


class AuthRequired(Exception):
    """Raised when a page route needs a signed-in user."""


def current_user(request: Request, db: SessionDep) -> models.User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.get(models.User, user_id)


CurrentUser = Annotated[models.User | None, Depends(current_user)]


def require_page_user(user: CurrentUser) -> models.User:
    if user is None:
        raise AuthRequired()
    return user


PageUser = Annotated[models.User, Depends(require_page_user)]


def require_api_user(user: CurrentUser) -> models.User:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user


ApiUser = Annotated[models.User, Depends(require_api_user)]
