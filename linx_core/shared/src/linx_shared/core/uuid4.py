from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator


def ensure_uuid_v4(value: object) -> UUID:
    """Normaliza e exige UUID versão 4.

    Aceita ``str`` ou ``UUID``. Rejeita formato inválido, UUID nulo e
    qualquer versão que não seja 4, levantando ``ValueError`` para que
    FastAPI/Pydantic respondam 422.
    """
    if isinstance(value, UUID):
        uuid_value = value
    elif isinstance(value, str):
        try:
            uuid_value = UUID(value)
        except ValueError as exc:
            raise ValueError("must be a valid UUID") from exc
    else:
        raise ValueError("must be a valid UUID")

    if uuid_value.version != 4:
        raise ValueError("must be a version 4 UUID")

    return uuid_value


UUID4 = Annotated[UUID, BeforeValidator(ensure_uuid_v4)]

__all__ = ["UUID4", "ensure_uuid_v4"]
