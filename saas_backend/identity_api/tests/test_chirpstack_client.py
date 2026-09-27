from unittest.mock import MagicMock

import grpc
from chirpstack_api import api

from identity_api.chirpstack_client import ChirpStackClient


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
