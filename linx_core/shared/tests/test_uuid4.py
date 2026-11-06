from uuid import UUID, uuid1, uuid3, uuid4, uuid5

import pytest
from pydantic import BaseModel, ValidationError

from linx_shared.core.uuid4 import UUID4, ensure_uuid_v4

_NAMESPACE = UUID("00000000-0000-0000-0000-000000000000")


class _Model(BaseModel):
    value: UUID4


def test_ensure_uuid_v4_accepts_uuid_object_v4() -> None:
    value = uuid4()
    assert ensure_uuid_v4(value) is value


def test_ensure_uuid_v4_accepts_string_v4() -> None:
    value = str(uuid4())
    result = ensure_uuid_v4(value)
    assert isinstance(result, UUID)
    assert result.version == 4


@pytest.mark.parametrize(
    "value",
    [
        uuid1(),
        uuid3(_NAMESPACE, "abc"),
        uuid5(_NAMESPACE, "abc"),
        UUID(int=0),
        str(uuid1()),
        str(uuid3(_NAMESPACE, "abc")),
        str(uuid5(_NAMESPACE, "abc")),
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_ensure_uuid_v4_rejects_non_v4(value: object) -> None:
    with pytest.raises(ValueError, match="version 4"):
        ensure_uuid_v4(value)


@pytest.mark.parametrize("value", ["not-a-uuid", "3f3b3", "12345"])
def test_ensure_uuid_v4_rejects_invalid_format(value: str) -> None:
    with pytest.raises(ValueError, match="valid UUID"):
        ensure_uuid_v4(value)


def test_ensure_uuid_v4_rejects_wrong_type() -> None:
    with pytest.raises(ValueError, match="valid UUID"):
        ensure_uuid_v4(12345)


def test_model_accepts_v4_string() -> None:
    value = str(uuid4())
    assert _Model.model_validate({"value": value}).value == UUID(value)


def test_model_rejects_v1() -> None:
    with pytest.raises(ValidationError):
        _Model.model_validate({"value": str(uuid1())})


def test_model_rejects_nil() -> None:
    with pytest.raises(ValidationError):
        _Model.model_validate(
            {"value": "00000000-0000-0000-0000-000000000000"}
        )
