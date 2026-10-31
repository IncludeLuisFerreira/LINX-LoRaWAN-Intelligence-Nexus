DEVICE_PROFILES_DIR ?= chirpstack-device-profiles

import-device-profiles:
	docker compose run --rm --entrypoint sh --user root \
		-v "$(CURDIR)/$(DEVICE_PROFILES_DIR):/device-profiles:ro" \
		chirpstack -c 'chirpstack -c /etc/chirpstack import-device-profiles -d /device-profiles'
