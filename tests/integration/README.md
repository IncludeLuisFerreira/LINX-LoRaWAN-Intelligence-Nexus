# Testes de integração

Cada **tipo** de teste de integração vive em sua própria subpasta, com o
`conftest.py` que sobe a stack daquele tipo. Os artefatos compartilhados
(dependências, `poetry.lock`, `run.sh`, este README) ficam na raiz de
`tests/integration/`.

```
tests/integration/
├── pyproject.toml      # dependências compartilhadas (pytest, pika, ...)
├── poetry.lock
├── run.sh              # wrapper: instala deps e roda o pytest
├── README.md
└── telemetry/          # telemetria ponta-a-ponta (issue #43)
    ├── README.md
    ├── conftest.py
    ├── docker-compose.stack.yml
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

- **Serviços reais:** as suítes constroem as imagens a partir dos Dockerfiles
  reais dos serviços. Cada suíte declara apenas a montagem necessária em um
  compose próprio de teste (`docker-compose.stack.yml`), sem alterar os
  composes de aplicação.
- **Isolamento:** rede, projeto, portas e volumes próprios (`LINX_NETWORK`),
  para não tocar no ambiente de desenvolvimento.
- **Framework:** `pytest` para aplicação e integração. `unittest` (stdlib) é
  reservado às ferramentas de repositório em `scripts/tests/`, que precisam
  rodar sem dependências.
- **Diagnóstico:** se um serviço não subir, a suíte aborta listando o
  container fora do ar e como ver os logs.
