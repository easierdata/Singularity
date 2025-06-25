# Dockerfile for Singularity Piece Downloader
# This container provides a Linux environment to run the download-pieces.sh script
# with all necessary dependencies pre-installed.

FROM ubuntu:22.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Update package list and install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    nano \
    bash \
    coreutils \
    findutils \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m -s /bin/bash downloader

# Create directories for the script, downloads, and configs
RUN mkdir -p /downloads /app /app/configs /app/tests /app/.default_configs && \
    chown downloader:downloader -R /app && \ 
    chown downloader:downloader /downloads

# Set working directory
WORKDIR /app

# Copy the entrypoint script first
COPY entrypoint.sh /entrypoint.sh

# Copy the shell scripts
COPY download-pieces.sh /app/
COPY monitor-downloads.sh /app/
COPY tests/ /app/tests

# Copy the configs directory
COPY configs/ /app/configs/
COPY configs/ /app/.default_configs/

# Make all shell scripts executable and set ownership
RUN chmod +x /entrypoint.sh /app/*.sh && \
    chown -R downloader:downloader /app/

# Switch to non-root user
USER downloader

# Set the downloads and configs directories as volume mount points
VOLUME ["/downloads", "/app/configs"]

# Set the entry script as the container's entrypoint
ENTRYPOINT ["/entrypoint.sh"]
