from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from linx.db.base import get_db
from linx.models.application import Application
from linx.models.tenant import Tenant
from linx.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)

router = APIRouter(prefix="/api/v1/tenant", tags=["Application"])


@router.post(
    "/{tenant_id}/applications",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationResponse,
)
def create_application(
    tenant_id: UUID,
    payload: ApplicationCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    new_application = Application(
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(new_application)
    db.commit()
    db.refresh(new_application)
    response.headers["Location"] = (
        f"/api/v1/tenant/{tenant_id}/applications/{new_application.id}"
    )
    return new_application


@router.get(
    "/{tenant_id}/applications", response_model=list[ApplicationResponse]
)
def list_applications(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    applications = (
        db.query(Application).filter(Application.tenant_id == tenant_id).all()
    )
    return applications


@router.get(
    "/{tenant_id}/applications/{application_id}",
    response_model=ApplicationResponse,
)
def get_application(
    tenant_id: UUID, application_id: UUID, db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found!")
    return application


@router.patch(
    "/{tenant_id}/applications/{application_id}",
    response_model=ApplicationResponse,
)
def update_application(
    tenant_id: UUID,
    application_id: UUID,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found!")

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(application, key, value)

    db.commit()
    db.refresh(application)
    return application


@router.delete(
    "/{tenant_id}/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_application(
    tenant_id: UUID, application_id: UUID, db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found!")

    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.tenant_id == tenant_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found!")

    db.delete(application)
    db.commit()
    return None
