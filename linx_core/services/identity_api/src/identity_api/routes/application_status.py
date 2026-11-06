from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from linx_shared.db.base import get_db
from linx_shared.models.application import Application
from linx_shared.models.application_instance import ApplicationInstance
from linx_shared.schemas.application import (
    ApplicationStatusResponse,
    ApplicationStatusValue,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1", tags=["Application"])


@router.get(
    "/applications/{application_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=ApplicationStatusResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Application ou sua instância não encontrada."
        }
    },
)
def get_application_status(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    """Retorna o status do container da aplicação lido do banco.

    A fonte da verdade é a tabela `application_instances`, atualizada pelo
    jobs_worker a cada ciclo de provisionamento. Não inspeciona o Docker
    diretamente: o valor reflete o resultado do último ciclo processado.
    """
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found!",
        )

    instance = (
        db.query(ApplicationInstance)
        .filter(ApplicationInstance.app_id == application_id)
        .one_or_none()
    )
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application instance not found!",
        )

    return ApplicationStatusResponse(
        app_id=instance.app_id,
        status=cast(ApplicationStatusValue, instance.status),
        container_id=instance.container_id,
        port=instance.port,
        provisioned_at=instance.provisioned_at,
    )
