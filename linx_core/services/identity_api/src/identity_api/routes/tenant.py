import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import get_db
from linx_shared.models.tenant import Tenant
from linx_shared.schemas.tenant import (
    TenantCreate,
    TenantResponse,
    TenantUpdate,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.dependencies import get_chirpstack_client

router = APIRouter(prefix="/api/v1/tenant", tags=["Tenant"])

logger = logging.getLogger(__name__)


def _delete_tenant_best_effort(
    chirpstack: ChirpStackClient, tenant_id: str
) -> None:
    try:
        chirpstack.delete_tenant(tenant_id)
    except ExternalServiceError:
        logger.warning(
            "Failed to delete tenant %s in ChirpStack; continuing", tenant_id
        )


# --- Dependência Reutilizável ---
def get_tenant_or_404(
    tenant_id: UUID, db: Session = Depends(get_db)
) -> Tenant:
    """Busca um tenant ou retorna 404. Usado por GET, PATCH e DELETE."""
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found!"
        )
    return tenant


@router.post(
    "/", status_code=status.HTTP_201_CREATED, response_model=TenantResponse
)
def create_tenant(
    payload: TenantCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    try:
        chirpstack_tenant_id = chirpstack.create_tenant(
            payload.name, payload.description
        )
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create tenant in ChirpStack: {exc.message}",
        ) from exc

    try:
        tenant_uuid = UUID(chirpstack_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ChirpStack returned invalid tenant ID: {chirpstack_tenant_id}",
        )

    new_tenant = Tenant(
        id=tenant_uuid,
        name=payload.name,
        description=payload.description,
    )
    db.add(new_tenant)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        _delete_tenant_best_effort(chirpstack, chirpstack_tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist tenant!",
        ) from None
    db.refresh(new_tenant)

    response.headers["Location"] = str(
        request.url_for("get_tenant", tenant_id=new_tenant.id)
    )
    return new_tenant


@router.get(
    "", status_code=status.HTTP_200_OK, response_model=list[TenantResponse]
)
def list_tenants(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    return tenants


@router.get(
    "/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
def get_tenant(tenant: Tenant = Depends(get_tenant_or_404)):
    return tenant


@router.patch(
    "/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
def update_tenant(
    payload: TenantUpdate,
    tenant: Tenant = Depends(get_tenant_or_404),
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    update_data = payload.model_dump(exclude_unset=True)
    name = update_data.get("name", tenant.name)
    description = update_data.get("description", tenant.description)

    for key, value in update_data.items():
        setattr(tenant, key, value)
    db.commit()
    db.refresh(tenant)

    try:
        chirpstack.update_tenant(str(tenant.id), name, description)
    except ExternalServiceError:
        logger.warning(
            "ChirpStack update failed for tenant %s; DB already updated",
            tenant.id,
        )

    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant: Tenant = Depends(get_tenant_or_404),
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    try:
        chirpstack.delete_tenant(str(tenant.id))
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to delete tenant in ChirpStack: {exc.message}",
        ) from exc

    db.delete(tenant)
    db.commit()
    return None
