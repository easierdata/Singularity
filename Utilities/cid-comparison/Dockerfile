# Alpine-based ultra-slim image for maximum size reduction
FROM ghcr.io/data-preservation-programs/singularity:main AS singularity-source

FROM alpine:latest AS kubo-downloader
RUN apk add --no-cache wget tar
WORKDIR /tmp
RUN wget -q https://github.com/ipfs/kubo/releases/download/v0.35.0/kubo_v0.35.0_linux-amd64.tar.gz && \
    tar -xzf kubo_v0.35.0_linux-amd64.tar.gz && \
    strip kubo/ipfs || true

# Final stage: Ultra-minimal Alpine
FROM alpine:latest

# Install only essential runtime dependencies for Alpine
RUN apk add --no-cache \
    bash \
    jq \
    bc \
    ca-certificates \
    libc6-compat \
    coreutils \
    util-linux \
    && rm -rf /var/cache/apk/*

# Copy binaries
COPY --from=singularity-source /app/singularity /usr/local/bin/singularity
COPY --from=kubo-downloader /tmp/kubo/ipfs /usr/local/bin/ipfs

# Create user (Alpine way)
ARG PUID=1000
ARG PGID=1000
RUN addgroup -g ${PGID} appgroup && \
    adduser -u ${PUID} -G appgroup -h /home/appuser -s /bin/bash -D appuser && \
    mkdir -p /data /home/appuser/{config,.default-config} && \
    chown -R appuser:appgroup /data /home/appuser

# Copy application files
COPY --chown=appuser:appgroup scripts/ /home/appuser/scripts/
COPY --chown=appuser:appgroup entrypoint.sh /home/appuser/entrypoint.sh
COPY --chown=appuser:appgroup config/ /home/appuser/.default-config/
COPY --chown=appuser:appgroup config/ /home/appuser/config/

# Set permissions and create convenient symlinks
RUN chmod +x /home/appuser/scripts/*.sh /home/appuser/entrypoint.sh /usr/local/bin/* && \
    ln -s /home/appuser/entrypoint.sh /usr/local/bin/menu && \
    ln -s /home/appuser/entrypoint.sh /usr/local/bin/open-menu && \
    ln -s /home/appuser/entrypoint.sh /usr/local/bin/start

ENV PATH="/usr/local/bin:${PATH}"
USER appuser
WORKDIR /home/appuser
VOLUME ["/data"]
ENTRYPOINT ["/home/appuser/entrypoint.sh"]