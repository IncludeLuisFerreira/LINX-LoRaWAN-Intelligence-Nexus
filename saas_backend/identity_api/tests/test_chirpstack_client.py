from unittest.mock import MagicMock

import grpc
import pytest
from chirpstack_api import api
from linx_shared.core.exceptions import ExternalServiceError

from identity_api.chirpstack_client import ChirpStackClient


class _FakeRpcError(grpc.RpcError):
    def details(self) -> str:
        return "device already exists"


def test_create_device_propagates_token_and_device(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)
    device = api.Device(dev_eui="1122334455667788", name="sensor-01")

    client.create_device(device)

    fake_stub.Create.assert_called_once()
    args, kwargs = fake_stub.Create.call_args
    assert args[0].device.dev_eui == "1122334455667788"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_channel_created_from_host_when_none_provided(monkeypatch):
    monkeypatch.setattr(grpc, "insecure_channel", MagicMock())

    ChirpStackClient("localhost:8080", "tok")

    grpc.insecure_channel.assert_called_once_with("localhost:8080")


def test_explicit_channel_avoids_creating_new_one(monkeypatch):
    fake_channel = MagicMock()
    monkeypatch.setattr(grpc, "insecure_channel", MagicMock())

    ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    grpc.insecure_channel.assert_not_called()


def test_create_device_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Create.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.create_device(api.Device(dev_eui="1122334455667788"))

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "create_device"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)


def test_delete_device_propagates_dev_eui_and_token(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.delete_device("1122334455667788")

    fake_stub.Delete.assert_called_once()
    args, kwargs = fake_stub.Delete.call_args
    assert args[0].dev_eui == "1122334455667788"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_delete_device_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.Delete.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.delete_device("1122334455667788")

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "delete_device"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)
