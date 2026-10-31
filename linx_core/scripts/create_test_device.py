import argparse
import sys

from chirpstack_api import api
from linx_shared.core.exceptions import ExternalServiceError

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cria um device de teste no ChirpStack via ChirpStackClient. "
            "Lê CHIRPSTACK_HOST e CHIRPSTACK_API_TOKEN do ambiente."
        )
    )
    parser.add_argument("dev_eui", help="DevEUI em 16 hex (ex: 0102030405060708)")
    parser.add_argument("application_id", help="UUID da Application no ChirpStack")
    parser.add_argument(
        "device_profile_id", help="UUID do Device Profile no ChirpStack"
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Nome do device (default: test-<dev_eui>)",
    )
    parser.add_argument(
        "--join-eui",
        default="0000000000000000",
        help="JoinEUI em 16 hex (default: 0000000000000000)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not settings.chirpstack_api_token:
        print(
            "CHIRPSTACK_API_TOKEN vazio. Defina o token no .env "
            "(ou via env) antes de rodar.",
            file=sys.stderr,
        )
        return 1

    client = ChirpStackClient(settings.chirpstack_host, settings.chirpstack_api_token)
    device = api.Device(
        dev_eui=args.dev_eui,
        name=args.name or f"test-{args.dev_eui}",
        application_id=args.application_id,
        device_profile_id=args.device_profile_id,
        join_eui=args.join_eui,
    )

    try:
        client.create_device(device)
    except ExternalServiceError as exc:
        print(f"Falha ao criar device: {exc}", file=sys.stderr)
        return 1

    print(f"Device criado: {args.dev_eui} (name={device.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
