import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import get_db
from linx_shared.models.application import Application
from linx_shared.models.tenant import Tenant
from linx_shared.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.dependencies import get_chirpstack_client

router = APIRouter(prefix="/api/v1/tenant", tags=["Application"])

logger = logging.getLogger(__name__)


def _delete_application_best_effort(
    chirpstack: ChirpStackClient, application_id: str
) -> None:
    try:
        chirpstack.delete_application(application_id)
    except ExternalServiceError:
        logger.warning(
            "Failed to delete application %s in ChirpStack; continuing",
            application_id,
        )


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
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found!",
        )

    try:
        chirpstack_application_id = chirpstack.create_application(
            str(tenant_id), payload.name, payload.description
        )
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create application in ChirpStack: {exc.message}",
        ) from exc

    try:
        application_uuid = UUID(chirpstack_application_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ChirpStack returned invalid application ID: {chirpstack_application_id}",
        )

    new_application = Application(
        id=application_uuid,
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(new_application)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        _delete_application_best_effort(chirpstack, chirpstack_application_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist application!",
        ) from None
    db.refresh(new_application)
    response.headers["Location"] = (
        f"/api/v1/tenant/{tenant_id}/applications/{new_application.id}"
    )
    return new_application


@router.get(
    "/{tenant_id}/applications",
    status_code=status.HTTP_200_OK,
    response_model=list[ApplicationResponse],
)
def list_applications(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found!",
        )

    applications = (
        db.query(Application).filter(Application.tenant_id == tenant_id).all()
    )
    return applications


@router.get(
    "/{tenant_id}/applications/{application_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApplicationResponse,
)
def get_application(
    tenant_id: UUID, application_id: UUID, db: Session = Depends(get_db)
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found!",
        )

    application = db.get(Application, application_id)
    if not application or application.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )
    return application


@router.patch(
    "/{tenant_id}/applications/{application_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApplicationResponse,
)
def update_application(
    tenant_id: UUID,
    application_id: UUID,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found!",
        )

    application = db.get(Application, application_id)
    if not application or application.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )

    update_data = payload.model_dump(exclude_unset=True)
    name = update_data.get("name", application.name)
    description = update_data.get("description", application.description)

    for key, value in update_data.items():
        setattr(application, key, value)
    db.commit()
    db.refresh(application)

    try:
        chirpstack.update_application(str(application_id), name, description)
    except ExternalServiceError:
        logger.warning(
            "ChirpStack update failed for application %s; DB already updated",
            application_id,
        )

    return application


@router.delete(
    "/{tenant_id}/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_application(
    tenant_id: UUID,
    application_id: UUID,
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found!",
        )

    application = db.get(Application, application_id)
    if not application or application.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )

    try:
        chirpstack.delete_application(str(application_id))
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to delete application in ChirpStack: {exc.message}",
        ) from exc

    db.delete(application)
    db.commit()
    return None
