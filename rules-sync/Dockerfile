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

# Create a non‑root user
RUN useradd -m -r syncuser && chown -R syncuser:syncuser /app
USER syncuser

EXPOSE 5002

CMD ["python", "sync-server.py"]
