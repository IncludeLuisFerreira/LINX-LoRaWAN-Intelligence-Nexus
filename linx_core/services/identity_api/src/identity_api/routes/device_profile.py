from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import get_db
from linx_shared.models.application import Application
from linx_shared.schemas.device_profile import DeviceProfileResponse
from sqlalchemy.orm import Session

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.dependencies import get_chirpstack_client

router = APIRouter(prefix="/api/v1/device-profile", tags=["device profile"])


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[DeviceProfileResponse],
)
def list_device_profiles(
    app_id: UUID,
    db: Session = Depends(get_db),
    chirpstack_client: ChirpStackClient = Depends(get_chirpstack_client),
):
    application = db.get(Application, app_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )

    try:
        return [
            DeviceProfileResponse(id=p.id, name=p.name)
            for p in chirpstack_client.list_device_profiles(
                str(application.tenant_id)
            )
        ]
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list device profiles: {exc.message}",
        ) from exc
