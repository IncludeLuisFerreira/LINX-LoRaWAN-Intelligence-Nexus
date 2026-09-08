from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from linx.db.base import get_db
from linx.models.tenant import Tenant
from linx.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/api/v1/tenant", tags=["Tenant"])


@router.post(
    "/", status_code=status.HTTP_201_CREATED, response_model=TenantResponse
)
def create_tenant(
    payload: TenantCreate, response: Response, db: Session = Depends(get_db)
):
    new_tenant = Tenant(name=payload.name, description=payload.description)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    response.headers["Location"] = f"/api/v1/tenant/{new_tenant.id}"
    return new_tenant


@router.get("", response_model=list[TenantResponse])
def list_tenants(db: Session = Depends(get_db)):
    tenants = db.query(Tenant).all()
    return tenants


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: UUID, payload: TenantUpdate, db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(tenant, key, value)

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    db.delete(tenant)
    db.commit()
    return None
