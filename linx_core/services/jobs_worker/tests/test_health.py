from contextlib import contextmanager
from unittest.mock import MagicMock

from jobs_worker import health


def test_check_reaches_postgres_and_rabbitmq(monkeypatch) -> None:
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(health, "engine", engine)

    opened: list[str] = []

    @contextmanager
    def fake_open_channel(url: str):
        opened.append(url)
        yield MagicMock()

    monkeypatch.setattr(health, "open_channel", fake_open_channel)

    health.check()

    connection.execute.assert_called_once()
    assert opened == [health.settings.rabbitmq_amqp_url]
