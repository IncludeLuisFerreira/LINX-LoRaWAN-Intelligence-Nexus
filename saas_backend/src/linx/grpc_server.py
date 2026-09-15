import logging
from concurrent import futures
from uuid import UUID

import grpc
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from linx.core.config import settings
from linx.db.base import SessionLocal
from linx.grpc import saas_agent_pb2, saas_agent_pb2_grpc
from linx.models.application import Application

logger = logging.getLogger(__name__)


class AgentBridgeServicer(saas_agent_pb2_grpc.AgentBridgeServicer):
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def GetAppConfig(self, request, context):
        try:
            app_id = UUID(request.app_id)
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"app_id inválido: {request.app_id}",
            )

        try:
            with self._session_factory() as session:
                app = session.scalar(
                    select(Application).where(Application.id == app_id)
                )
            db_url = make_url(settings.database_url)
        except SQLAlchemyError:
            logger.exception("Falha ao consultar a aplicação %s", app_id)
            context.abort(
                grpc.StatusCode.UNAVAILABLE, "Banco de dados indisponível"
            )

        if app is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Aplicação {request.app_id} não encontrada!",
            )

        return saas_agent_pb2.AppConfig(
            app_id=str(app.id),
            db_host=db_url.host or "",
            db_port=db_url.port or 0,
            db_name=db_url.database or "",
            db_user=db_url.username or "",
            db_password=db_url.password or "",
            mqtt_topic=f"application/{app.id}/device/+/event/up",
        )

    def ReportViolation(self, request, context):
        """Placeholder até a persistência de violações (Sprint 6)."""
        return saas_agent_pb2.Ack(ok=False, error="not implemented")


def create_server(
    servicer: AgentBridgeServicer | None = None,
) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    if servicer is None:
        servicer = AgentBridgeServicer()
    saas_agent_pb2_grpc.add_AgentBridgeServicer_to_server(servicer, server)
    bind_address = f"{settings.grpc_host}:{settings.grpc_port}"
    if server.add_insecure_port(bind_address) == 0:
        raise RuntimeError(
            f"Não foi possível fazer bind do servidor gRPC em {bind_address}"
        )
    return server


def serve():
    server = create_server()
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
