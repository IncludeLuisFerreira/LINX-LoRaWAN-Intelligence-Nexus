FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# A API é consumida em same-origin (/api/v1) e o nginx faz proxy para o backend.
ARG VITE_API_URL=/api/v1
# Mocks (MSW) são opt-in: desligados por padrão para não vazar dados fake no deploy.
ARG VITE_ENABLE_MOCKS=false
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_ENABLE_MOCKS=$VITE_ENABLE_MOCKS

RUN npm run build

FROM nginx:alpine

# O entrypoint do nginx substitui ${BACKEND_URL} no template via envsubst.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

# Destino do proxy /api/. O default mantém o nginx de pé em execução isolada;
# em compose use o nome do serviço (ex.: -e BACKEND_URL=http://identity_api:8000).
ENV BACKEND_URL=http://127.0.0.1:8000

# Destino do proxy /ws/ (WebSocket de telemetria).
ENV WS_BACKEND_URL=http://127.0.0.1:8000

# Valor de SERVICE_TOKEN injetado no header X-Service-Token do proxy /api.
# O default mantém o nginx de pé em execução isolada (docker run, smoke de CI):
# sem ele, o envsubst deixa `${SERVICE_TOKEN}` literal e o `nginx -t` falha.
# Em compose use o mesmo SERVICE_TOKEN do identity_api (client/docker-compose.yml).
# O valor default não é um segredo válido e é rejeitado pelo identity_api.
ENV SERVICE_TOKEN=unconfigured-service-token

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
