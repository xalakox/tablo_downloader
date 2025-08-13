# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tablo Downloader is a Python application that queries Tablo DVR devices to manage and download recordings as MPEG4 files using ffmpeg. The project uses Docker for consistent deployment and execution.

## Docker-Based Development Commands

### Configuration
Create a `.env` file from the template for sensitive variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

### Building the Docker Image
```bash
make docker-build
```

### Core Operations via Docker

1. **Update the recordings database**:
   ```bash
   make docker-updatedb
   ```

2. **Dump all recordings**:
   ```bash
   make docker-dump
   ```

3. **Download latest episode of a show**:
   ```bash
   make docker-download-latest SHOW_MATCH="Show Name"
   ```

4. **Upload recordings to Put.io**:
   ```bash
   make docker-upload-putio
   ```

5. **Interactive shell in container**:
   ```bash
   make docker-shell
   ```

### Environment Variables (.env file)
- `TABLO_IPS`: IP address(es) of Tablo device(s)
- `SHOW_MATCH`: Show title to match for downloading
- `PUTIO_TOKEN`: Put.io OAuth token (get from https://app.put.io/account/api)
- `DEBUG`: Set to "true" for debug logging
- `DB_PATH`: Database path (default: /data/tablo.db)
- `RECORDINGS_PATH`: Recordings directory (default: /data/recordings)

### Data Persistence
- Local `./data` directory is mounted to `/data` in container
- Database stored at `./data/tablo.db`
- Recordings saved to `./data/recordings/`

## Code Architecture

### Core Components

**tablo_downloader/tablo.py**
- Main CLI entry point via `main()` function
- Key functions:
  - `parse_args_and_settings()`: CLI argument parsing
  - `create_or_update_recordings_database()`: Updates local DB with Tablo recordings
  - `download_recording()`: Downloads individual recordings using ffmpeg
  - `find_recording_by_show_title()`: Matches shows by title for downloading

**tablo_downloader/apis.py**
- API wrapper for Tablo device communication
- Key functions:
  - `local_server_info()`: Discovers local Tablo devices
  - `server_recordings()`: Lists all recordings
  - `recording_details()`: Gets metadata for recordings
  - `watch_recording()`: Gets streaming playlist URLs

**tablo_downloader/putio_uploader.py**
- Handles uploading recordings to Put.io cloud storage
- Tracks uploaded files to avoid duplicates
- Key features:
  - `upload_directory()`: Uploads all video files from recordings directory
  - Maintains upload history in `/data/putio_uploads.json`
  - Supports dry-run mode for testing

**entrypoint.sh**
- Docker container entrypoint
- Handles environment variable configuration
- Executes updatedb followed by either dump or download based on SHOW_MATCH

### Configuration

Settings can be provided via:
1. Command-line arguments
2. Environment variables (in Docker)
3. `~/.tablodlrc` JSON config file

## Testing

Tests use pytest with mocked API responses:
```bash
python3 -m pytest tests/
```

## Important Notes

- ffmpeg is required for downloading (included in Docker image)
- Local discovery may not work when connected to VPN
- Database updates are incremental after initial scan
- Recordings are saved with metadata-based filenames