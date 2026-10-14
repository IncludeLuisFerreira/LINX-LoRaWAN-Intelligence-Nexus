# Testes de integração

Cada **tipo** de teste de integração vive em sua própria subpasta, com o
`conftest.py` que sobe a stack daquele tipo. Os artefatos compartilhados
(dependências, `poetry.lock`, `run.sh`, este README) ficam na raiz de
`tests/integration/`.

```
tests/integration/
├── pyproject.toml      # dependências compartilhadas (pytest, rabbitpy, ...)
├── poetry.lock
├── run.sh              # wrapper: instala deps e roda o pytest
├── README.md
└── telemetry/          # telemetria ponta-a-ponta (issue #43)
    ├── README.md
    ├── conftest.py
    ├── docker-compose.override.yml
    ├── test.env
    └── test_telemetry_pipeline.py
```

## Como rodar

```bash
make integration          # atalho na raiz do repo
# ou
tests/integration/run.sh
# ou, direto:
poetry -C tests/integration run pytest
```

Uma suíte específica:

```bash
poetry -C tests/integration run pytest telemetry
```

Requisitos: Docker em execução e Poetry no PATH.

## Tipos disponíveis

| Pasta       | Cobre                                                             |
| ----------- | ----------------------------------------------------------------- |
| `telemetry` | Uplink MQTT até os contratos do frontend (REST + WebSocket)        |

## Princípios

- **Reúso:** as suítes usam os compose existentes do repositório
  (`deploy/docker-compose.yml`, etc.) via override mínimo — sem redefinir
  serviços, o que mantém uma única fonte de verdade.
- **Diagnóstico:** se um serviço não subir, a suíte aborta listando o
  container fora do ar e como ver os logs.
