from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from linx.db.base import get_db
from linx.models.tenant import Tenant
from linx.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/api/v1/tenant", tags=["Tenant"])


# --- Dependência Reutilizável ---
def get_tenant_or_404(
    tenant_id: UUID, db: Session = Depends(get_db)
) -> Tenant:
    """Busca um tenant ou retorna 404. Usado por GET, PATCH e DELETE."""
    tenant = db.get(Tenant, tenant_id)  # Forma otimizada do SQLAlchemy para PK
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
):
    new_tenant = Tenant(name=payload.name, description=payload.description)

    # Dica: Se o nome precisar ser único, envolva db.commit()
    # em um try/except capturando sqlalchemy.exc.IntegrityError
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)

    # Gera a URL de forma dinâmica e independente do prefixo
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
    # Paginação adicionada para evitar memory leak ou sobrecarga do banco
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    return tenants


@router.get(
    "/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
def get_tenant(tenant: Tenant = Depends(get_tenant_or_404)):
    # A dependência já fez todo o trabalho sujo de buscar e validar
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
):
    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(tenant, key, value)

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant: Tenant = Depends(get_tenant_or_404), db: Session = Depends(get_db)
):
    db.delete(tenant)
    db.commit()
    return None
