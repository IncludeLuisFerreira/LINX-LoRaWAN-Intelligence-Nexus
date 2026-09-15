import logging
from concurrent import futures
from uuid import UUID

import grpc
from sqlalchemy import select
from sqlalchemy.engine import make_url

from linx.core.config import settings
from linx.db.base import SessionLocal
from linx.grpc import saas_agent_pb2, saas_agent_pb2_grpc
from linx.models.application import Application

logger = logging.getLogger(__name__)

GRPC_HOST = "0.0.0.0"
GRPC_PORT = 50051


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
            return None

        with self._session_factory() as session:
            app = session.scalar(
                select(Application).where(Application.id == app_id)
            )

        if app is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Aplicação {request.app_id} não encontrada!",
            )

        db_url = make_url(settings.database_url)

        return saas_agent_pb2.AppConfig(
            app_id=str(app.id),
            db_host=db_url.host or "",
            db_port=db_url.port or 0,
            db_name=db_url.database or "",
            db_user=db_url.username or "",
            db_password=db_url.password or "",
            mqtt_topic=f"application/{app.id}/device/+/event/up",
        )

    def IngestTelemetry(self, request, context):
        """Placeholder para ingestão de telemetria."""
        return saas_agent_pb2.Ack(ok=True)

    def SyncRule(self, request, context):
        """Placeholder para sincronização de regras."""
        return saas_agent_pb2.Ack(ok=True)

    def ReportViolation(self, request, context):
        """Placeholder para relatório de violações."""
        return saas_agent_pb2.Ack(ok=True)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    saas_agent_pb2_grpc.add_AgentBridgeServicer_to_server(
        AgentBridgeServicer(), server
    )
    port = server.add_insecure_port(f"{GRPC_HOST}:{GRPC_PORT}")
    if port == 0:
        logger.error(
            "Não foi possível fazer bind do servidor gRPC em %s:%s",
            GRPC_HOST,
            GRPC_PORT,
        )
        return
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
