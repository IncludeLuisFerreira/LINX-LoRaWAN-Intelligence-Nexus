# ChirpStack Docker example

This repository contains a skeleton to setup the [ChirpStack](https://www.chirpstack.io)
open-source LoRaWAN Network Server (v4) using [Docker Compose](https://docs.docker.com/compose/).

**Note:** Please use this `docker-compose.yml` file as a starting point for testing
but keep in mind that for production usage it might need modifications. 

## Directory layout

* `docker-compose.yml`: the docker-compose file containing the services
* `configuration/chirpstack`: directory containing the ChirpStack configuration files
* `configuration/chirpstack-gateway-bridge`: directory containing the ChirpStack Gateway Bridge configuration
* `configuration/mosquitto`: directory containing the Mosquitto (MQTT broker) configuration
* `configuration/postgresql/initdb/`: directory containing PostgreSQL initialization scripts

## Configuration

This setup is pre-configured for all regions. You can either connect a ChirpStack Gateway Bridge
instance (v3.14.0+) to the MQTT broker (port 8883, TLS — issue #81) or connect a
Semtech UDP Packet Forwarder. The plaintext listener on 1883 was removed:
non-TLS connections are rejected (connection refused). Please note that:

* You must prefix the MQTT topic with the region.
  Please see the region configuration files in the `configuration/chirpstack` for a list
  of topic prefixes (e.g. eu868, us915_0, au915_0, as923_2, ...).
* The protobuf marshaler is configured.

This setup also comes with two instances of the ChirpStack Gateway Bridge. One
is configured to handle the Semtech UDP Packet Forwarder data (port 1700), the
other is configured to handle the Basics Station protocol (port 3001). Both
instances are by default configured for EU868 (using the `eu868` MQTT topic
prefix).

### Reconfigure regions

ChirpStack has at least one configuration of each region enabled. You will find
the list of `enabled_regions` in `configuration/chirpstack/chirpstack.toml`.
Each entry in `enabled_regions` refers to the `id` that can be found in the
`region_XXX.toml` file. This `region_XXX.toml` also contains a `topic_prefix`
configuration which you need to configure the ChirpStack Gateway Bridge
UDP instance (see below).

#### ChirpStack Gateway Bridge (UDP)

Within the `docker-compose.yml` file, you must replace the `eu868` prefix in the
`INTEGRATION__..._TOPIC_TEMPLATE` configuration with the MQTT `topic_prefix` of
the region you would like to use (e.g. `us915_0`, `au915_0`, `in865`, ...).

#### ChirpStack Gateway Bridge (Basics Station)

Within the `docker-compose.yml` file, you must update the configuration file
that the ChirpStack Gateway Bridge instance must used. The default is
`chirpstack-gateway-bridge-basicstation-eu868.toml`. For available
configuration files, please see the `configuration/chirpstack-gateway-bridge`
directory.

# Data persistence

PostgreSQL and Redis data is persisted in Docker volumes, see the `docker-compose.yml`
`volumes` definition.

## Requirements

Before using this `docker-compose.yml` file, make sure you have [Docker](https://www.docker.com/community-edition)
installed and `openssl` available on the host.

### MQTT TLS (issue #81)

Generate the CA and the broker server certificate **before** `docker compose up`:

```bash
infra/scripts/gen-mosquitto-certs.sh
# opcional: MQTT_TLS_HOST=<ip-ou-hostname-publico> infra/scripts/gen-mosquitto-certs.sh
```

This writes `infra/configuration/mosquitto/certs/{ca.crt,server.crt,server.key}`
and the CA private key in `infra/configuration/mosquitto/private/ca.key`
(both gitignored). Only `ca.crt` is mounted into the client containers;
`ca.key` never leaves the host and the broker gets only `ca.crt`, `server.crt`
and `server.key` (0640, owned by uid 1883). The script is idempotent — use
`FORCE=1` to regenerate. The broker listens only on `8883` (published on `127.0.0.1`);
ChirpStack, both gateway bridges and the routing service connect with
`ssl://mosquitto:8883` and validate the server against `ca.crt`.
Username/password + ACL from issue #208 remain in force.

Smoke test from the host:

```bash
# falha: nao ha listener plaintext na 1883
mosquitto_sub -h 127.0.0.1 -p 1883 -t '#'
# funciona (use uma identidade do mosquitto.passwd)
mosquitto_sub -h localhost -p 8883 --cafile infra/configuration/mosquitto/certs/ca.crt \
  -u chirpstack -P '<senha>' -t '#'
```

## Importing device repository

To import the [chirpstack-device-profiles](https://github.com/chirpstack/chirpstack-device-profiles)
repository (optional step), run the following command:

```bash
make import-device-profiles
```

This imports the device-profiles repository located in the local
`chirpstack-device-profiles` directory (override with `DEVICE_PROFILES_DIR=<path>`)
by executing the ChirpStack import command. Please note that for this step you
need to have the `make` command installed.

## Usage

To start the ChirpStack simply run:

```bash
$ docker compose up
```

### Required environment

`docker-compose.yml` no longer hardcodes the PostgreSQL password. The `postgres`
service requires `POSTGRES_PASSWORD` to be provided, otherwise `docker compose`
aborts with an explicit error (fail closed — the stack must not boot with a
placeholder credential).

Create an `infra/.env` file (or export the variable) with a real value:

```bash
$ echo 'POSTGRES_PASSWORD=troque-por-uma-senha-forte' > .env
$ docker compose up
```

There is no `infra/.env.example` in this directory; if you add one, keep
`POSTGRES_PASSWORD` as an obviously-invalid placeholder so a copy still fails
startup until the operator sets a real value.

After all the components have been initialized and started, you should be able
to open http://localhost:8080/ in your browser.

##

The example includes the [ChirpStack REST API](https://github.com/chirpstack/chirpstack-rest-api).
You should be able to access the UI by opening http://localhost:8090 in your browser.

**Note:** It is recommended to use the [gRPC](https://www.chirpstack.io/docs/chirpstack/api/grpc.html)
interface over the [REST](https://www.chirpstack.io/docs/chirpstack/api/rest.html) interface.
