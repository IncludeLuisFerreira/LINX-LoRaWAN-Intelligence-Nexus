from concurrent import futures

import grpc

# from sqlalchemy import select
from sqlalchemy.orm import Session

from linx.db.base import engine
from linx.grpc import saas_agent_pb2, saas_agent_pb2_grpc

# from linx.models.application import Application


class AgentBridgeServicer(saas_agent_pb2_grpc.AgentBridgeServicer):
    def GetAppConfig(self, request, context):
        with Session(engine):
            #   stmt = select(Application).where(Application.id == request.app_id)
            #   app = session.scalar(stmt)

            """
            if not app:
                context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"Aplicação {request.app_id}não encontrada!",
                )
            """
        mqtt_topic = f"application/{request.app_id}/device/+/event/up"

        return saas_agent_pb2.AppConfig(
            db_host="localhost", db_port=5432, mqtt_topic=mqtt_topic
        )

    def IngestTelemetry(self, request, context):
        """Placeholder para ingestão de telemetria."""
        return saas_agent_pb2.Ack(success=True, message="OK")

    def SyncRule(self, request, context):
        """Placeholder para sincronização de regras."""
        return saas_agent_pb2.Ack(success=True, message="OK")

    def ReportViolation(self, request, context):
        """Placeholder para relatório de violações."""
        return saas_agent_pb2.Ack(success=True, message="OK")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    saas_agent_pb2_grpc.add_AgentBridgeServicer_to_server(
        AgentBridgeServicer(), server
    )
    server.add_insecure_port("0.0.0.0:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
