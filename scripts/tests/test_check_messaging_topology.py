import tempfile
import unittest
from pathlib import Path

from scripts.check_messaging_topology import validate

BASE_OK = """
services:
  rabbitmq:
    image: rabbitmq:3-management-alpine
networks:
  linx-network:
    external: true
    name: ${LINX_NETWORK:-linx-network}
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class ValidateTests(unittest.TestCase):
    def test_accepts_single_broker_in_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(root, "deploy/docker-compose.yml", "services:\n  db: {}\n")
            self.assertEqual(validate(root), [])

    def test_rejects_two_broker_definitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(
                root,
                "deploy/docker-compose.yml",
                "services:\n  rabbitmq:\n    image: rabbitmq:3-management\n",
            )
            self.assertTrue(
                any("rabbitmq_duplicata" in v for v in validate(root))
            )

    def test_rejects_broker_outside_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                "linx_core/docker-compose.yml",
                "services:\n"
                "  rabbitmq:\n"
                "    image: rabbitmq:3-management-alpine\n",
            )
            self.assertTrue(
                any("rabbitmq_not_in_base" in v for v in validate(root))
            )

    def test_rejects_default_credentials_in_app_compose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(
                root,
                "deploy/docker-compose.yml",
                "services:\n"
                "  routing:\n"
                "    environment:\n"
                "      - RABBIT_URL=amqp://${RABBITMQ_DEFAULT_USER}:x@rabbitmq:5672/\n",
            )
            self.assertTrue(
                any(
                    "rabbitmq_credencial_default" in v
                    for v in validate(root)
                )
            )

    def test_accepts_override_with_compose_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(
                root,
                "tests/integration/telemetry/docker-compose.override.yml",
                "services:\n"
                "  rabbitmq:\n"
                "    ports: !override\n"
                '      - "127.0.0.1:5673:5672"\n',
            )
            self.assertEqual(validate(root), [])

class RepositoryTest(unittest.TestCase):
    def test_repository_has_single_broker(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(validate(root), [])

if __name__ == "__main__":
    unittest.main()
