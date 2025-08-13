#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# If arguments are passed to the script, execute them directly
# This allows running custom commands like the putio uploader
if [ $# -gt 0 ]; then
  exec "$@"
fi

# Otherwise, continue with the default tablo downloader behavior
# Ensure data directories exist (Docker will create /data, but maybe not subdirs if needed later)
# For now, we assume the app handles creation if needed or paths are direct files.

# Default command options for path
# DB_PATH and RECORDINGS_PATH are set by Dockerfile
# tablo.py will use these if --database_folder/--recordings_directory are not given explicitly
# or if the env vars are not picked up by python os.getenv
# However, explicitly passing them makes behavior clear.
CMD_OPTS="--database_folder $DB_PATH --recordings_directory $RECORDINGS_PATH"

# Append --loglevel debug if DEBUG env var is set (optional)
if [ -n "$DEBUG" ] && [ "$DEBUG" = "true" ]; then
  CMD_OPTS="$CMD_OPTS --loglevel debug"
fi

# Append Tablo IPs if TABLO_IPS environment variable is set
if [ -n "$TABLO_IPS" ]; then
  echo "Using Tablo IPs from TABLO_IPS: $TABLO_IPS"
  CMD_OPTS="$CMD_OPTS --tablo_ips $TABLO_IPS"
else
  echo "TABLO_IPS not set, relying on auto-discovery or config file."
fi

echo "Using the CMD_OPTS: $CMD_OPTS"
# Update the database first
echo "Updating database..."
tldl $CMD_OPTS --updatedb

# Check if SHOW_MATCH environment variable is provided
if [ -n "$SHOW_MATCH" ]; then
  echo "SHOW_MATCH detected: $SHOW_MATCH"
  echo "Attempting to download latest episode for '$SHOW_MATCH'..."
  # tldl will use SHOW_MATCH env var if --show is not provided by CMD_OPTS
  # but we explicitly pass it here for clarity from the env var.
  tldl $CMD_OPTS --show "$SHOW_MATCH"
else
  echo "No SHOW_MATCH provided. Performing full dump..."
  # This is based on your Makefile's dump command
  tldl --log_level debug $CMD_OPTS --dump
fi

echo "Processing complete."
