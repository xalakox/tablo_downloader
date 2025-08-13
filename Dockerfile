# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (ffmpeg for video processing)
# Best practice: update apt-get, install, then clean up in one RUN layer to reduce image size.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the local code to the container
COPY setup.py README.md LICENSE ./
COPY tablo_downloader/ ./tablo_downloader/

# Install any needed packages specified in setup.py
RUN pip install --no-cache-dir .

# Install requests package (required for put.io uploads)
# Note: requests is already in setup.py, so this is covered by the above pip install 

# Define mountable VOLUME for database and recordings
VOLUME /data

# Set default environment variables for data paths
ENV DB_PATH=/data/tablo.db
ENV RECORDINGS_PATH=/data/recordings

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Specify the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
