import logging
from uuid import UUID

from argon2 import PasswordHasher
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

from identity_api.security import verify_service_token

logger = logging.getLogger(__name__)

password_hasher = PasswordHasher()

router = APIRouter(
    prefix="/api/v1/user",
    tags=["Users"],
    dependencies=[Depends(verify_service_token)],
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def get_user_or_404(user_id: UUID, db: Session = Depends(get_db)) -> User:
    """Busca um usuário pelo id ou retorna 404."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found!"
        )
    return user


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
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
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered!",
        )

    response.headers["Location"] = str(
        request.url_for("get_user", user_id=new_user.id)
    )
    return new_user


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[UserResponse],
)
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(User).order_by(User.created_at).offset(skip).limit(limit)
    ).all()


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
)
def get_user(user: User = Depends(get_user_or_404)):
    return user


@router.patch(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
)
def update_user(
    payload: UserUpdate,
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
):
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "password":
            if value is not None:
                user.password_hash = hash_password(value)
        elif value is not None:
            setattr(user, key, value)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered!",
        )

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
):
    db.delete(user)
    db.commit()
    return None
