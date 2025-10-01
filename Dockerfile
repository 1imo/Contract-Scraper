# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install OpenVPN and runtime tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       openvpn iproute2 iptables curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# System deps for building wheels (if needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure OpenVPN config path is predictable
ENV OVPN_CONFIG=/app/data/Windscribe-Atlanta-Mountain.ovpn

# Create directory for OpenVPN runtime
RUN mkdir -p /run/openvpn

# Add entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default command uses entrypoint to start VPN then app
ENTRYPOINT ["/entrypoint.sh"]
