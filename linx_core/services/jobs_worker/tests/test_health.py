from unittest.mock import MagicMock

from jobs_worker import health


def test_check_reaches_postgres_and_rabbitmq(monkeypatch) -> None:
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(health, "engine", engine)

    rabbit = MagicMock()
    connection_factory = MagicMock(return_value=rabbit)
    monkeypatch.setattr(health.pika, "BlockingConnection", connection_factory)

    health.check()

    connection.execute.assert_called_once()
    rabbit.channel.assert_called_once()
    rabbit.close.assert_called_once()
