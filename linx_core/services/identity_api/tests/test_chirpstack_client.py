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


def test_create_device_keys_propagates_dev_eui_app_key_and_token(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    client.create_device_keys(
        "1122334455667788", "00112233445566778899aabbccddeeff"
    )

    fake_stub.CreateKeys.assert_called_once()
    args, kwargs = fake_stub.CreateKeys.call_args
    assert args[0].device_keys.dev_eui == "1122334455667788"
    assert args[0].device_keys.nwk_key == "00112233445566778899aabbccddeeff"
    assert args[0].device_keys.app_key == "00112233445566778899aabbccddeeff"
    assert kwargs["metadata"] == [("authorization", "Bearer tok")]


def test_create_device_keys_wraps_rpc_error(monkeypatch):
    fake_channel = MagicMock()
    fake_stub = MagicMock()
    fake_stub.CreateKeys.side_effect = _FakeRpcError()
    monkeypatch.setattr(api, "DeviceServiceStub", lambda channel: fake_stub)

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.create_device_keys(
            "1122334455667788", "00112233445566778899aabbccddeeff"
        )

    error = exc_info.value
    assert error.service == "chirpstack"
    assert error.operation == "create_device_keys"
    assert error.message == "device already exists"
    assert isinstance(error.original_error, grpc.RpcError)


def test_close_closes_channel():
    fake_channel = MagicMock()

    client = ChirpStackClient("localhost:8080", "tok", channel=fake_channel)
    client.close()

    fake_channel.close.assert_called_once()


def test_tls_enabled_uses_secure_channel(monkeypatch):
    credentials = MagicMock()
    monkeypatch.setattr(
        grpc, "ssl_channel_credentials", MagicMock(return_value=credentials)
    )
    monkeypatch.setattr(grpc, "secure_channel", MagicMock())
    monkeypatch.setattr(grpc, "insecure_channel", MagicMock())

    ChirpStackClient("chirpstack:8080", "tok", use_tls=True)

    grpc.ssl_channel_credentials.assert_called_once_with(
        root_certificates=None
    )
    grpc.secure_channel.assert_called_once_with("chirpstack:8080", credentials)
    grpc.insecure_channel.assert_not_called()


def test_tls_reads_ca_cert_file(monkeypatch, tmp_path):
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_bytes(b"CERT")
    credentials = MagicMock()
    monkeypatch.setattr(
        grpc, "ssl_channel_credentials", MagicMock(return_value=credentials)
    )
    monkeypatch.setattr(grpc, "secure_channel", MagicMock())

    ChirpStackClient(
        "chirpstack:8080", "tok", use_tls=True, ca_cert=str(ca_cert)
    )

    grpc.ssl_channel_credentials.assert_called_once_with(
        root_certificates=b"CERT"
    )
    grpc.secure_channel.assert_called_once_with("chirpstack:8080", credentials)
