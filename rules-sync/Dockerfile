FROM python:3.12-slim

WORKDIR /app

# Install debugging tools and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    dnsutils \
    netcat-openbsd \
    telnet \
    vim-tiny \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir flask requests

# Copy the sync server script
COPY sync-server.py .

# Create a non-root user with explicit UID/GID that matches your host/docker-compose (1000:1000)
# This helps avoid permission problems on the shared volume
RUN groupadd -g 1000 syncuser && \
    useradd -m -u 1000 -g 1000 -r syncuser

# Pre-create the target directory and give ownership to the app user
# This is crucial for the volume mount
RUN mkdir -p /etc/falco/rules.d && \
    chown -R syncuser:syncuser /app /etc/falco

USER syncuser

EXPOSE 5002

CMD ["python", "sync-server.py"]
