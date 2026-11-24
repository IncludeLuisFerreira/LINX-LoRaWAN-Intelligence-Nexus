import ipaddress
import logging
import secrets
import socket
from collections.abc import Iterable
from concurrent import futures
from uuid import UUID

import grpc
from linx_shared.db.base import SessionLocal
from linx_shared.grpc import linx_agent_pb2, linx_agent_pb2_grpc
from linx_shared.models.application import Application
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from agent_bridge.config import settings

logger = logging.getLogger(__name__)

AUTH_METADATA_KEY = "authorization"
BEARER_PREFIX = "Bearer "
MIN_AGENT_TOKEN_LENGTH = 32
PLACEHOLDER_AGENT_TOKENS = frozenset(
    {"changeme", "change-me", "change-me-in-production"}
)
_UNAUTHENTICATED_DETAILS = "Not authorized"


def _extract_bearer_token(
    invocation_metadata: Iterable[tuple[str, str]] | None,
) -> str | None:
    """Retorna o token do metadado ``authorization: Bearer <token>``."""
    for key, value in invocation_metadata or ():
        if key.lower() == AUTH_METADATA_KEY and value.startswith(
            BEARER_PREFIX
        ):
            prefix_len = len(BEARER_PREFIX)
            return value[prefix_len:].strip()
    return None


def _auth_value(auth_context: dict, key: str) -> str:
    """Retorna o primeiro valor de uma chave do ``auth_context`` do gRPC."""
    values = auth_context.get(key) or ()
    if not values:
        return ""
    value = values[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _log_mtls_peer(context) -> None:
    """Registra o certificado do cliente validado no handshake mTLS.

    O contexto de uma chamada sem certificado não expõe chaves ``x509_*``;
    nesse caso nada é logado. A chamada é defensiva porque testes usam
    contextos fakes que não implementam ``auth_context()``.
    """
    auth_context_fn = getattr(context, "auth_context", None)
    if not callable(auth_context_fn):
        return
    try:
        auth_context = auth_context_fn() or {}
    except Exception:  # pragma: no cover - contexto pode ser encerrado
        logger.debug("auth_context do gRPC indisponível", exc_info=True)
        return
    if not any(key.startswith("x509_") for key in auth_context):
        return
    peer = (
        _auth_value(auth_context, "x509_common_name")
        or _auth_value(auth_context, "x509_subject_alternative_name")
        or "desconhecido"
    )
    transport = _auth_value(auth_context, "transport_security_type") or "ssl"
    logger.info(
        "Handshake mTLS confirmado: peer=%s transport=%s", peer, transport
    )


def authorize(context) -> None:
    """Valida o token de serviço do agente nos metadados da chamada.

    Falha fechada e em tempo constante: qualquer chamada sem o metadado
    ``authorization`` correto é recusada com UNAUTHENTICATED, sem vazar o
    motivo nem o segredo esperado. Quando mTLS está ativo, o certificado do
    cliente já foi validado no handshake e a identidade é logada.
    """
    _log_mtls_peer(context)
    expected = settings.agent_service_token
    if not expected:
        logger.error(
            "AGENT_SERVICE_TOKEN não configurado; recusando chamada gRPC."
        )
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED, _UNAUTHENTICATED_DETAILS
        )

    provided = _extract_bearer_token(context.invocation_metadata()) or ""
    if not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED, _UNAUTHENTICATED_DETAILS
        )


def ensure_agent_service_token() -> None:
    """Rejeita o startup quando o token de serviço está ausente ou fraco.

    Mesma filosofia de validação de ``identity_api``: sem segredo robusto o
    servidor gRPC não sobe, pois a autorização por metadados seria inútil.
    """
    token = settings.agent_service_token or ""
    if not token.strip():
        raise RuntimeError("AGENT_SERVICE_TOKEN must not be blank.")
    if token in PLACEHOLDER_AGENT_TOKENS:
        raise RuntimeError(
            "AGENT_SERVICE_TOKEN uses a known placeholder value; "
            "set a unique random secret."
        )
    if len(token) < MIN_AGENT_TOKEN_LENGTH:
        raise RuntimeError(
            f"AGENT_SERVICE_TOKEN must be at least "
            f"{MIN_AGENT_TOKEN_LENGTH} characters long."
        )


class AgentBridgeServicer(linx_agent_pb2_grpc.AgentBridgeServicer):
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def GetAppConfig(self, request, context):
        authorize(context)
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

        return linx_agent_pb2.AppConfig(
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
        authorize(context)
        return linx_agent_pb2.Ack(ok=False, error="not implemented")


def _build_bind_address(host: str, port: int) -> str:
    if ":" in host:
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def _read_tls_file(path: str, label: str) -> bytes:
    """Lê um arquivo de credencial em bytes, falhando com erro explícito."""
    try:
        with open(path, "rb") as handle:
            content = handle.read()
    except OSError as err:
        raise RuntimeError(
            f"Não foi possível ler {label} em {path}: {err}"
        ) from err
    if not content:
        raise RuntimeError(f"Arquivo de {label} vazio: {path}")
    return content


def _build_server_credentials() -> grpc.ServerCredentials | None:
    """Monta as credenciais mTLS do servidor, ou None em modo dev.

    São obrigatórios os três arquivos — certificado e chave do servidor e CA
    que assina os certificados dos clientes. Configuração parcial aborta o
    startup: TLS sem verificação do cliente não atende ao RNF-004. Sem nenhum
    caminho configurado o servidor permanece inseguro apenas para dev local.
    """
    cert_chain = settings.grpc_cert_chain_path
    private_key = settings.grpc_private_key_path
    ca_cert = settings.grpc_ca_cert_path
    if not any((cert_chain, private_key, ca_cert)):
        return None
    if not all((cert_chain, private_key, ca_cert)):
        raise RuntimeError(
            "mTLS do gRPC exige GRPC_CERT_CHAIN_PATH, "
            "GRPC_PRIVATE_KEY_PATH e GRPC_CA_CERT_PATH juntos "
            "(ou nenhum, apenas em dev)."
        )

    logger.info(
        "Carregando credenciais mTLS do gRPC: cert=%s key=%s ca=%s",
        cert_chain,
        private_key,
        ca_cert,
    )
    return grpc.ssl_server_credentials(
        [
            (
                _read_tls_file(private_key, "chave privada do servidor gRPC"),
                _read_tls_file(cert_chain, "certificado do servidor gRPC"),
            )
        ],
        root_certificates=_read_tls_file(ca_cert, "CA do gRPC"),
        require_client_auth=True,
    )


def create_server(
    servicer: AgentBridgeServicer | None = None,
) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    if servicer is None:
        servicer = AgentBridgeServicer()
    linx_agent_pb2_grpc.add_AgentBridgeServicer_to_server(servicer, server)
    bind_address = _build_bind_address(settings.grpc_host, settings.grpc_port)
    credentials = _build_server_credentials()
    if credentials is not None:
        port = server.add_secure_port(bind_address, credentials)
        logger.info(
            "gRPC com mTLS em %s: certificado do cliente obrigatório.",
            bind_address,
        )
    else:
        logger.warning(
            "Servindo gRPC em modo inseguro em %s sem mTLS. A autorização por "
            "metadado (AGENT_SERVICE_TOKEN) é a única barreira; configure "
            "GRPC_CERT_CHAIN_PATH, GRPC_PRIVATE_KEY_PATH e "
            "GRPC_CA_CERT_PATH para exigir mTLS.",
            bind_address,
        )
        port = server.add_insecure_port(bind_address)
    if port == 0:
        raise RuntimeError(
            f"Não foi possível fazer bind do servidor gRPC em {bind_address}"
        )
    return server


def is_grpc_serving(
    host: str | None = None,
    port: int | None = None,
    timeout: float = 1.0,
) -> bool:
    """Indica se há um servidor escutando no host/porta do gRPC."""
    target_host = settings.grpc_host if host is None else host
    target_port = settings.grpc_port if port is None else port
    if not target_host:
        target_host = "127.0.0.1"
    else:
        try:
            address = ipaddress.ip_address(target_host)
        except ValueError:
            pass
        else:
            if address.is_unspecified:
                target_host = "::1" if address.version == 6 else "127.0.0.1"
    if target_port == 0:
        return False
    try:
        with socket.create_connection(
            (target_host, target_port), timeout=timeout
        ):
            return True
    except (OSError, OverflowError, ValueError):
        return False


def serve():
    ensure_agent_service_token()
    server = create_server()
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
