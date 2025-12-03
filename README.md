# tablo-downloader (Docker Fork)
Query one or more Tablo devices to get and manage a list of recordings and
then download the recordings to local MPEG4 files using `ffmpeg`. This fork adds Docker support, Put.io cloud storage integration, and automated show downloading.

## New Features in This Fork
- 🐳 **Docker Support**: Run everything in containers for consistent deployment
- ☁️ **Put.io Integration**: Automatically upload recordings to Put.io cloud storage
- 📺 **Show Matching**: Download latest episodes by show name (fuzzy matching)
- 🔐 **Environment Variables**: Secure configuration via `.env` file
- 📁 **Improved Database**: Specify custom database paths and filenames

## Quick Start with Docker

### 1. Clone and Configure
```bash
git clone https://github.com/xalakox/tablo_downloader
cd tablo_downloader
cp .env.example .env
# Edit .env with your Tablo IP and Put.io token
```

### 2. Build Docker Image
```bash
make docker-build
```

### 3. Common Operations

#### Update recordings database
```bash
make docker-updatedb
```

#### Download latest episode of a specific show
```bash
make docker-download-latest SHOW_MATCH="Show Name"
```
If your Tablo is only reachable via Tailscale, set `TS_AUTHKEY` in `.env` and this target will bring up a Tailscale sidecar automatically.

#### Upload recordings to Put.io
```bash
make docker-upload-putio
```

#### Dump all recordings info
```bash
make docker-dump
```

## Configuration

### Environment Variables (.env file)
Create a `.env` file from the template:
```bash
cp .env.example .env
```

Configure these variables:
- `TABLO_IPS`: Your Tablo device IP address(es)
- `SHOW_MATCH`: Show title to match for downloading (optional)
- `PUTIO_TOKEN`: Your Put.io OAuth token (get from https://app.put.io/account/api)
- `DEBUG`: Set to "true" for verbose logging
- `TS_AUTHKEY`: Optional Tailscale auth key; when set, `docker-download-latest` will run through a Tailscale sidecar for Tablo access
- `TS_EXTRA_ARGS`: Extra flags passed to `tailscale up` (defaults to `--accept-routes` so subnet routes are used)
- `TS_UP_RESET`: Whether to pass `--reset` to `tailscale up` to clear prior non-default settings (default: true)
- `TS_TUN`: Tailscale tun mode (default: `tailscale0` for kernel routing; if you set userspace networking, the downloader will not get Tailscale routes)
- `TAILSCALED_ARGS`: Override args for `tailscaled` (default: `--statedir=/var/lib/tailscale --socket=/var/run/tailscale/tailscaled.sock --tun=$(TS_TUN)`)
- `TAILSCALE_WAIT_SECS`: How long to wait for the Tailscale sidecar to become ready (default: 60)

### Data Storage
- Database: `./data/tablo.db`
- Recordings: `./data/recordings/`
- Put.io upload tracking: `./data/putio_uploads.json`

## Traditional Installation (Python)

### Install
```bash
git clone https://github.com/xalakox/tablo_downloader
pip install ./tablo_downloader
```

Running the install will create two programs, `tldl` (Tablo downloader) and
`tldlapis` (Tablo downloader APIs).

### Configuration
You can provide default values for any flags in `~/.tablodlrc`. The format is
json. If you have a Tablo device whose IP is `192.168.1.25` and you want to
copy Tablo recordings to /Volume/Recordings, you should create a config
like the following:
```json
{
  "tablo_ips": "192.168.1.25",
  "recordings_directory": "/Volume/Recordings"
}
```
If you do not specify an IP (or IPs), either via a flag or in your
`~/.tablodlrc` file, the programs in this package will try to discover the
IPs of your Tablo device(s) automatically.

### Typical Usage
- `tldl --local_ips` - Print the IPs of any local Tablo devices.
- `tldl --updatedb` - Create/update a database of current tablo recordings. This takes several minutes to run initially but afterwards it runs quickly.
- `tldl --dump` - Print out a readable summary of every Tablo recording, including recording IDs.
- `tldl --download_recording --recording_id /recordings/sports/events/464898` - Download a Tablo recording.
- `tldl --show "Show Name"` - Download the latest episode of a show by name (fuzzy matching).

## Requirements
- Python 3.9+ (or Docker)
- ffmpeg (included in Docker image)
- Network access to Tablo device

## Notes
- Local discovery may not work if connected to a VPN.
- The Docker version includes all dependencies and is the recommended way to run.
- Put.io uploader tracks uploaded files to avoid duplicates.
