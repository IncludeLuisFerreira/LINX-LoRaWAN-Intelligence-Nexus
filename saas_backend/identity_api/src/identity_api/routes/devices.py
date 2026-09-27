from collections.abc import Generator
from uuid import UUID

from chirpstack_api import api
from fastapi import APIRouter, Depends, HTTPException, status
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import get_db
from linx_shared.models.application import Application
from linx_shared.models.device import Device
from linx_shared.schemas.device import DeviceCreate, DeviceResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.config import settings

router = APIRouter(prefix="/api/v1", tags=["Device"])


def get_chirpstack_client() -> Generator[ChirpStackClient, None, None]:
    client = ChirpStackClient(
        settings.chirpstack_host, settings.chirpstack_api_token
    )
    try:
        yield client
    finally:
        client.close()


def _delete_device_best_effort(
    chirpstack: ChirpStackClient, dev_eui: str
) -> None:
    try:
        chirpstack.delete_device(dev_eui)
    except ExternalServiceError:
        pass


@router.get(
    "/devices",
    status_code=status.HTTP_200_OK,
    response_model=list[DeviceResponse],
)
def list_devices(app_id: UUID, db: Session = Depends(get_db)):
    application = db.get(Application, app_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )

    devices = db.query(Device).filter(Device.app_id == app_id).all()
    return devices


@router.post(
    "/devices",
    status_code=status.HTTP_201_CREATED,
    response_model=DeviceResponse,
)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    if not settings.chirpstack_device_profile_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ChirpStack device profile is not configured!",
        )

    application = db.get(Application, payload.app_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )

    existing = (
        db.query(Device).filter(Device.dev_eui == payload.dev_eui).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device already exists!",
        )

    chirpstack_device = api.Device(
        dev_eui=payload.dev_eui,
        name=f"device-{payload.dev_eui}",
        application_id=str(payload.app_id),
        device_profile_id=settings.chirpstack_device_profile_id,
        join_eui=payload.join_eui,
    )
    try:
        chirpstack.create_device(chirpstack_device)
        chirpstack.create_device_keys(payload.dev_eui, payload.app_key)
    except ExternalServiceError as exc:
        _delete_device_best_effort(chirpstack, payload.dev_eui)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to provision device in ChirpStack: {exc.message}",
        ) from exc

    new_device = Device(
        dev_eui=payload.dev_eui,
        app_id=payload.app_id,
        join_eui=payload.join_eui,
        app_key=payload.app_key,
    )
    db.add(new_device)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _delete_device_best_effort(chirpstack, payload.dev_eui)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device already exists!",
        ) from None
    db.refresh(new_device)
    return new_device


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    chirpstack: ChirpStackClient = Depends(get_chirpstack_client),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found!",
        )

    try:
        chirpstack.delete_device(device.dev_eui)
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to delete device in ChirpStack: {exc.message}",
        ) from exc

    db.delete(device)
    db.commit()
    return None
