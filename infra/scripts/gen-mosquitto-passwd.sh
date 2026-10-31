#!/usr/bin/env bash
# Gera infra/configuration/mosquitto/config/mosquitto.passwd com hashes reais
# para as identidades do mosquitto.acl (chirpstack, routing, healthcheck).
#
# Uso:
#   MQTT_CHIRPSTACK_PASSWORD=... MQTT_ROUTING_PASSWORD=... \
#     infra/scripts/gen-mosquitto-passwd.sh
#
# Em dev, usa defaults claramente marcados (dev-only). Em producao, exija as
# duas senhas via ambiente; sem elas o script falha. O `mosquitto_passwd` roda
# dentro da imagem eclipse-mosquitto (docker), entao o host nao precisa da
# ferramenta instalada.
#
# O arquivo gerado NAO e versionado (.gitignore); commitar hash de senha real
# e proibido.
set -euo pipefail

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../configuration/mosquitto/config" && pwd)"
PASSWD_FILE="${CONFIG_DIR}/mosquitto.passwd"
ACL_FILE="${CONFIG_DIR}/mosquitto.acl"

CHIRPSTACK_USER="${MQTT_CHIRPSTACK_USER:-chirpstack}"
ROUTING_USER="${MQTT_ROUTING_USER:-routing}"
HEALTHCHECK_USER="${MQTT_HEALTHCHECK_USER:-healthcheck}"
CHIRPSTACK_PASSWORD="${MQTT_CHIRPSTACK_PASSWORD:-}"
ROUTING_PASSWORD="${MQTT_ROUTING_PASSWORD:-}"
HEALTHCHECK_PASSWORD="${MQTT_HEALTHCHECK_PASSWORD:-}"

if [[ "${ENV:-dev}" != "dev" ]]; then
  for pair in "MQTT_CHIRPSTACK_PASSWORD=${CHIRPSTACK_PASSWORD}" \
    "MQTT_ROUTING_PASSWORD=${ROUTING_PASSWORD}" \
    "MQTT_HEALTHCHECK_PASSWORD=${HEALTHCHECK_PASSWORD}"; do
    if [[ -z "${pair#*=}" ]]; then
      echo "ERROR: ${pair%%=*} obrigatorio fora de dev" >&2
      exit 1
    fi
  done
else
  CHIRPSTACK_PASSWORD="${CHIRPSTACK_PASSWORD:-chirpstack-dev-change-me}"
  ROUTING_PASSWORD="${ROUTING_PASSWORD:-routing-dev-change-me}"
  HEALTHCHECK_PASSWORD="${HEALTHCHECK_PASSWORD:-healthcheck-dev-change-me}"
  echo "WARNING: usando senhas DEV — troque MQTT_*_PASSWORD em producao" >&2
fi

if [[ ! -f "${ACL_FILE}" ]]; then
  echo "ERROR: ${ACL_FILE} nao encontrado" >&2
  exit 1
fi

# -c cria/recomeca o arquivo; -b recebe a senha na linha de comando (batch);
# sem -B = hash forte com salt (padrao do mosquitto_passwd >= 2.0).
docker run --rm \
  -v "${CONFIG_DIR}:/lynx-mosquitto-config" \
  eclipse-mosquitto:2 \
  sh -eu -c '
    mosquitto_passwd -c -b /lynx-mosquitto-config/mosquitto.passwd "$1" "$2"
    mosquitto_passwd -b /lynx-mosquitto-config/mosquitto.passwd "$3" "$4"
    mosquitto_passwd -b /lynx-mosquitto-config/mosquitto.passwd "$5" "$6"
    # broker roda como usuario nao-root (uid/gid 1883) e so precisa LER;
    # 0644 e owner 1883:1883 (arquivo e root-owned no host, chmod/chown la
    # falham). best-effort: em rootless docker o chown pode falhar e o
    # mosquitto ainda le com 0644.
    chmod 0644 /lynx-mosquitto-config/mosquitto.passwd
    chmod 0644 /lynx-mosquitto-config/mosquitto.acl 2>/dev/null || true
    chown 1883:1883 /lynx-mosquitto-config/mosquitto.passwd 2>/dev/null || true
  ' sh \
    "${CHIRPSTACK_USER}" "${CHIRPSTACK_PASSWORD}" \
    "${ROUTING_USER}" "${ROUTING_PASSWORD}" \
    "${HEALTHCHECK_USER}" "${HEALTHCHECK_PASSWORD}"

echo "OK: ${PASSWD_FILE} gerado para: ${CHIRPSTACK_USER}, ${ROUTING_USER}, ${HEALTHCHECK_USER} (nao versionar)"
