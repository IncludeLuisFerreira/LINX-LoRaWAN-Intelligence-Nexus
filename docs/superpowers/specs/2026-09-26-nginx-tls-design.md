# Design — Issue #32: nginx com TLS (self-signed dev)

> Fecha a exigência **RNF-004** (comunicação HTTPS na borda da nuvem).
> Estratégia de certificado: **self-signed em dev**. Nginx roda como **container**
> na stack `deploy/docker-compose.yml`. A porta `8000` do `identity_api`
> **permanece publicada**.

## Contexto

O SaaS Backend é exposto hoje em HTTP puro na porta `8000` pelo
`deploy/docker-compose.yml` (`identity_api`). Não há terminação TLS: o
`curl`/navegador fala HTTP diretamente com o Uvicorn. Esta issue adiciona uma
borda TLS na frente do backend.

## Arquitetura

Adicionar um serviço `nginx` (`nginx:alpine`) à stack `deploy/`, na mesma rede
Docker dos demais serviços, tornando-se a borda TLS:

```
cliente --https:443--> nginx --http--> identity_api:8000
cliente --http:80---> nginx --301--> https
```

- `443 ssl` (com `http2 on;`): proxy reverso para `http://identity_api:8000`.
- `80`: `return 301 https://$host$request_uri`.
- O upstream usa `resolver 127.0.0.11 valid=10s ipv6=off;` + variável
  (`set $backend ...; proxy_pass http://$backend;`) para re-resolver o DNS
  interno do Docker, evitando cache do IP do `identity_api`.
- `identity_api:8000` continua publicada (acesso direto legado preservado).
- Certificado self-signed gerado no host por script e montado **read-only**;
  nenhuma chave privada é versionada (`.gitignore` já cobre `*.pem`/`*.key`).

O nginx não fala gRPC (`50051`) nem serve o frontend — fora de escopo.

## Componentes

| Arquivo | Ação | Responsabilidade |
| --- | --- | --- |
| `deploy/nginx/nginx.conf` | criar | server `80` (redirect p/ HTTPS) + server `443 ssl` (proxy p/ `identity_api:8000`, headers `X-Forwarded-*`, health) |
| `deploy/scripts/gen-self-signed-cert.sh` | criar | gera `deploy/certs/fullchain.pem` + `privkey.pem` via `openssl`, idempotente, SAN = `localhost` + host/IP informado |
| `deploy/docker-compose.yml` | editar | serviço `nginx` (portas `80:80`/`443:443`, volumes `nginx.conf` e `certs/` read-only, `depends_on: identity_api service_healthy`) |
| `deploy/.env.example` | editar | variável `TLS_CERT_HOST` (host/SAN opcional; default `localhost`) |
| `.gitignore` | editar | ignorar `deploy/certs/` explicitamente |
| `docs/saas_backend/README.md` (runbook) | editar | passo a passo TLS + verificação `curl -kI https://<host>/health`; instrui rodar o script gerador antes do `up` |
| `saas_backend/identity_api/src/identity_api/main.py` | editar | `/health` passa a aceitar `GET` e `HEAD` (o critério pede `curl -I` = 200) |
| `saas_backend/identity_api/tests/test_main.py` | editar | teste `test_health_supports_head` (TDD) |

## Nginx

`deploy/nginx/nginx.conf`:

- `server` na `80` com `return 301 https://$host$request_uri;`.
- `server` na `443 ssl` com `ssl_certificate /etc/nginx/certs/fullchain.pem;`
  e `ssl_certificate_key /etc/nginx/certs/privkey.pem;`.
- `location / { proxy_pass http://$backend; }` (com
  `set $backend "identity_api:8000";` e `resolver 127.0.0.11 valid=10s ipv6=off;`)
  e `proxy_set_header Host $host;`, `X-Real-IP`, `X-Forwarded-For`,
  `X-Forwarded-Proto $scheme;`.
- `ssl_protocols TLSv1.2 TLSv1.3;` e `http2 on;`.

O host `identity_api` é o nome do serviço no Compose; não versionar IP.

## Ajuste de backend (HEAD em `/health`)

Como o critério de aceite usa `curl -I` (que envia `HEAD`), e o `identity_api`
respondia `405` a `HEAD` (`allow: GET`), o endpoint `/health` passa a aceitar
`GET` e `HEAD` via `@app.api_route("/health", methods=["GET", "HEAD"])`. É uma
mudança mínima, coberta por `test_health_supports_head` em TDD.

## Geração do certificado

`deploy/scripts/gen-self-signed-cert.sh`:

- Variáveis: `TLS_CERT_HOST` (default `localhost`), `TLS_CERT_DIR`
  (default `deploy/certs`) e `TLS_CERT_DAYS` (default `365`).
- Gera chave RSA 2048 + cert de 365 dias. O SAN é condicional: se
  `TLS_CERT_HOST` for um IPv4, usa `DNS:localhost,IP:127.0.0.1,IP:$TLS_CERT_HOST`;
  caso contrário, `DNS:localhost,DNS:$TLS_CERT_HOST,IP:127.0.0.1`.
- Idempotente: se `fullchain.pem` e `privkey.pem` já existem, não regenera
  (a menos que `FORCE=1`).
- Falha com mensagem clara se `openssl` não estiver disponível.

## Fluxo de dados

1. Cliente abre `https://<host>/health`.
2. nginx termina o TLS e encaminha `GET /health` para `identity_api:8000`.
3. `identity_api` responde `{"status":"ok","db":true}`; o nginx devolve ao
   cliente.
4. Cliente abrindo `http://<host>/health` recebe `301` para `https://...`.

## Erros e casos de borda

- **Certificado ausente:** o container `nginx` falha ao subir (erro claro no
  log). O runbook instrui rodar o script gerador antes do `docker compose up`.
- **Sem domínio:** o SAN cobre `localhost` e o IP/host informado; `curl -k`
  e o navegador (com aviso de cert não confiável) funcionam.
- **Security Group:** as portas `80` e `443` precisam ser liberadas (não estão
  cobertas pela issue #31, que liberou 8000/50051/22). Registrado no runbook.
- **Conflito de porta:** se um processo no host já usa 80/443, o `up` falha;
  documentado.
- **Healthcheck do nginx:** usa `https://127.0.0.1/health` (e não `localhost`)
  porque `localhost` resolve para `::1` no container enquanto o nginx escuta
  IPv4.

## Critérios de aceite (issue #32)

- [x] HTTPS ativo na borda (porta 443) → serviço `nginx` com `listen 443 ssl`.
- [x] `curl -kI https://<host>/health` retorna `200` (TLS self-signed).
- [x] HTTP redireciona para HTTPS → `301` na porta 80.
- [x] Verificação `curl -vkI https://<host>/health` mostra o handshake TLS.

## Testes e verificação

- `docker compose -f deploy/docker-compose.yml config -q` (sintaxe válida).
- `bash deploy/scripts/gen-self-signed-cert.sh` gera os dois PEMs e é
  idempotente na segunda execução.
- Local (executado com sucesso): `docker compose up -d --build`, então:
  - `curl -kI https://localhost/health` → `HTTP/2 200`, `server: nginx`;
  - `curl -sI http://localhost/health` → `301`, `Location: https://localhost/health`;
  - `curl -vkI https://localhost/health` → TLSv1.3, ALPN `h2`, cert self-signed;
  - `curl -sI http://localhost:8000/health` → `200` (acesso direto preservado);
  - healthcheck do container `nginx` → `healthy`.
- Backend: `pytest identity_api/tests/test_main.py` com `test_health_supports_head`
  passando (a falha de `test_health_reports_real_database_as_up` é por ausência de
  Postgres, pré-existente).

## Fora de escopo

- Let's Encrypt/certbot real (exige domínio público).
- TLS no gRPC (`50051`).
- HTTPS no frontend (#73) e TLS 1.3 "em todas as camadas" (#78).
- mTLS entre serviços (Sprint 5).
- Fechar a porta `8000` para o mundo.
