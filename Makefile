# Load environment variables from .env file if it exists
-include .env
export

# Local (non-Docker) commands
updatedb:
	python3 -m tablo_downloader.tablo --tablo_ips $(TABLO_IPS) --updatedb --database_folder ./data/tablo.db

dump:
	python3 -m tablo_downloader.tablo --tablo_ips $(TABLO_IPS) --dump

download:
	python3 -m tablo_downloader.tablo --download_recording --recording_id /recordings/series/episodes/4011394 --recordings_directory ./data/recordings --tablo_ips $(TABLO_IPS) --overwrite -v

# Docker settings
DOCKER_IMAGE_NAME ?= tablo-downloader-app
DOCKER_TAG ?= latest
LOCAL_DATA_DIR := $(CURDIR)/data

# Default values if not set in .env
TABLO_IPS ?= 192.168.1.100
SHOW_MATCH ?= 
PUTIO_TOKEN ?= 
DEBUG ?= 

# Common Docker run options: mount local ./data to /data in container
# DB_PATH and RECORDINGS_PATH are set in Dockerfile to /data/tablo.db and /data/recordings
# These will be used by the app if --dbpath or --recpath are not specified (entrypoint.sh passes them)
# Pass TABLO_IPS and SHOW_MATCH as environment variables to the container.
# Use -it for interactive, --rm to remove container after exit.
DOCKER_RUN_OPTS = -it --rm \
	-v "$(LOCAL_DATA_DIR):/data" \
	-e TABLO_IPS="$(TABLO_IPS)" \
	-e SHOW_MATCH="$(SHOW_MATCH)" \
	-e DEBUG="$(DEBUG)"

.PHONY: all docker-build docker-shell docker-updatedb docker-dump docker-download-latest docker-upload-putio docker-upload-putio-newest ensure-data-dir

all: docker-build

ensure-data-dir:
	@mkdir -p $(LOCAL_DATA_DIR)/recordings

docker-build:
	@echo "Building Docker image $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)..."
	docker build -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) .

docker-shell: docker-build ensure-data-dir
	@echo "Starting shell in Docker container... Local ./data mounted to /data."
	docker run $(DOCKER_RUN_OPTS) --entrypoint /bin/sh $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

docker-updatedb: docker-build ensure-data-dir
	@echo "Updating database via Docker... Local ./data mounted to /data."
	@echo "Using TABLO_IPS=$(TABLO_IPS)"
	# entrypoint.sh handles the --updatedb command based on lack of SHOW_MATCH
	# To specifically run only updatedb, we can override entrypoint or have a specific arg in entrypoint
	# For now, we rely on entrypoint.sh running updatedb then exiting if SHOW_MATCH is not set.
	# To force ONLY updatedb, one might need to adjust entrypoint or pass a specific command.
	# The current entrypoint always runs updatedb first.
	# If SHOW_MATCH is empty, it will run updatedb then dump.
	# To make it just updatedb, we can set SHOW_MATCH to a dummy value that finds nothing or adjust entrypoint.
	# Simpler: entrypoint.sh runs updatedb. Then if no SHOW_MATCH, it DUMPS.
	# We want this command to JUST update DB. A direct command override is better.
	docker run $(DOCKER_RUN_OPTS) $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) tablo-downloader --recpath /data/recordings --tablo-ips "$(TABLO_IPS)" --updatedb

docker-dump: docker-build ensure-data-dir
	@echo "Dumping recordings database via Docker... Local ./data mounted to /data."
	@echo "Using TABLO_IPS=$(TABLO_IPS)"
	# entrypoint.sh by default will run updatedb, then dump if SHOW_MATCH is not set.
	docker run -i --rm -v "$(LOCAL_DATA_DIR):/data" -e TABLO_IPS="$(TABLO_IPS)" -e SHOW_MATCH="" -e DEBUG="$(DEBUG)" $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

docker-download-latest: docker-build ensure-data-dir
	@echo "Downloading latest via Docker... Local ./data mounted to /data."
	@if [ -z "$(SHOW_MATCH)" ]; then \
		echo "Error: SHOW_MATCH environment variable is not set."; \
		echo "Usage: make docker-download-latest SHOW_MATCH=\"Your Show Title Prefix\" [TABLO_IPS=\"x.x.x.x\"]"; \
		exit 1; \
	fi
	@echo "Using SHOW_MATCH=$(SHOW_MATCH)"
	@echo "Using TABLO_IPS=$(TABLO_IPS)"
	# entrypoint.sh will run updatedb, then download-latest because SHOW_MATCH is set.
	docker run $(DOCKER_RUN_OPTS) $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)

docker-upload-putio: docker-build ensure-data-dir
	@echo "Uploading recordings to put.io via Docker... Local ./data mounted to /data."
	@if [ -z "$(PUTIO_TOKEN)" ]; then \
		echo "Error: PUTIO_TOKEN environment variable is not set."; \
		echo "Usage: make docker-upload-putio PUTIO_TOKEN=\"your-putio-oauth-token\""; \
		echo "Get your token from: https://app.put.io/account/api"; \
		exit 1; \
	fi
	@echo "Uploading files from ./data/recordings to put.io..."
	docker run --rm -v "$(LOCAL_DATA_DIR):/data" -e PUTIO_TOKEN="$(PUTIO_TOKEN)" $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) \
		python3 -m tablo_downloader.putio_uploader \
		--token "$(PUTIO_TOKEN)" \
		--recordings-dir /data/recordings \
		--db-path /data/putio_uploads.json -v

docker-upload-putio-newest: docker-build ensure-data-dir
	@echo "Uploading newest recording to put.io via Docker... Local ./data mounted to /data."
	@if [ -z "$(PUTIO_TOKEN)" ]; then \
		echo "Error: PUTIO_TOKEN environment variable is not set."; \
		echo "Usage: make docker-upload-putio-newest PUTIO_TOKEN=\"your-putio-oauth-token\""; \
		echo "Get your token from: https://app.put.io/account/api"; \
		exit 1; \
	fi
	@echo "Uploading newest file from ./data/recordings to put.io (if not already uploaded)..."
	docker run --rm -v "$(LOCAL_DATA_DIR):/data" -e PUTIO_TOKEN="$(PUTIO_TOKEN)" $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) \
		python3 -m tablo_downloader.putio_uploader \
		--token "$(PUTIO_TOKEN)" \
		--recordings-dir /data/recordings \
		--db-path /data/putio_uploads.json \
		--newest-only -v
