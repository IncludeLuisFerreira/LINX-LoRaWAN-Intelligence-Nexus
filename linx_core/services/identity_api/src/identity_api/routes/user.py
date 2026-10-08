import logging
from typing import NoReturn
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from linx_shared.db.base import get_db
from linx_shared.models.user import User
from linx_shared.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity_api.security import hash_password, verify_service_token

logger = logging.getLogger(__name__)

EMAIL_UNIQUE_INDEX = "uq_user_email_lower"

AUTH_RESPONSES: dict[int | str, dict] = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Missing or invalid service token"
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Service token not configured"
    },
}

router = APIRouter(
    prefix="/api/v1/user",
    tags=["Users"],
    dependencies=[Depends(verify_service_token)],
)


def _is_email_conflict(exc: IntegrityError) -> bool:
    """True quando a violação é da unicidade case-insensitive do email."""
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == EMAIL_UNIQUE_INDEX


def _raise_email_conflict(db: Session, exc: IntegrityError) -> NoReturn:
    db.rollback()
    if _is_email_conflict(exc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered!",
        )
    raise exc


def get_user_or_404(user_id: UUID, db: Session = Depends(get_db)) -> User:
    """Busca um usuário pelo id ou retorna 404."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found!"
        )
    return user


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    responses={
        **AUTH_RESPONSES,
        status.HTTP_409_CONFLICT: {"description": "Email already registered"},
    },
)
def create_user(
    payload: UserCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    new_user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        note=payload.note or "",
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as exc:
        _raise_email_conflict(db, exc)

    logger.info("user.created user_id=%s", new_user.id)
    response.headers["Location"] = request.url_for(
        "get_user", user_id=new_user.id
    ).path
    return new_user


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[UserResponse],
    responses={**AUTH_RESPONSES},
)
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(User)
        .order_by(User.created_at, User.id)
        .offset(skip)
        .limit(limit)
    ).all()


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    responses={
        **AUTH_RESPONSES,
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def get_user(user: User = Depends(get_user_or_404)):
    return user


@router.patch(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    responses={
        **AUTH_RESPONSES,
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_409_CONFLICT: {"description": "Email already registered"},
    },
)
def update_user(
    payload: UserUpdate,
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
):
    password_changed = False
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "password":
            if value is not None:
                user.password_hash = hash_password(value)
                password_changed = True
        elif value is not None:
            setattr(user, key, value)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        _raise_email_conflict(db, exc)

    logger.info(
        "user.updated user_id=%s password_changed=%s",
        user.id,
        password_changed,
    )
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **AUTH_RESPONSES,
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def delete_user(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
):
    user.is_active = False
    db.commit()
    logger.info("user.deactivated user_id=%s", user.id)
    return None
