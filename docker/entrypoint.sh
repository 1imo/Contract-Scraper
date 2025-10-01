#!/bin/sh
set -euo pipefail

OVPN_CONFIG_PATH="${OVPN_CONFIG:-/app/data/Windscribe-Atlanta-Mountain.ovpn}"
OVPN_ARGS=""
LOG_DIR=/run/openvpn
LOG_FILE="$LOG_DIR/openvpn.log"
PID_FILE="$LOG_DIR/openvpn.pid"

mkdir -p "$LOG_DIR"

if [ ! -e /dev/net/tun ]; then
  mkdir -p /dev/net || true
  mknod /dev/net/tun c 10 200 || true
  chmod 600 /dev/net/tun || true
fi

if [ ! -f "$OVPN_CONFIG_PATH" ]; then
  echo "[entrypoint] OpenVPN config not found at $OVPN_CONFIG_PATH" >&2
  exit 1
fi

# If both username and password are provided, create a non-interactive auth file
if [ "${OVPN_AUTH_USERNAME:-}" != "" ] && [ "${OVPN_AUTH_PASSWORD:-}" != "" ]; then
  AUTH_FILE=$LOG_DIR/auth.txt
  umask 077
  printf "%s\n%s\n" "$OVPN_AUTH_USERNAME" "$OVPN_AUTH_PASSWORD" > "$AUTH_FILE"
  OVPN_ARGS="--auth-user-pass $AUTH_FILE"
  echo "[entrypoint] Using credentials from environment for OpenVPN auth."
fi

# Start OpenVPN with verbose logging
: > "$LOG_FILE"
echo "[entrypoint] Starting OpenVPN with config: $OVPN_CONFIG_PATH"
openvpn --config "$OVPN_CONFIG_PATH" $OVPN_ARGS --verb 4 --log "$LOG_FILE" --daemon --writepid "$PID_FILE"

# Wait for any tun interface to come up, and fail fast if OpenVPN exits
TRIES=0
while true; do
  # Detect any tun interface (tun0, tun1, etc.)
  if ip -o link show | grep -qE ": tun[0-9]+:"; then
    TUN_IFACE=$(ip -o link show | awk -F': ' '/: tun[0-9]+:/{print $2; exit}')
    echo "[entrypoint] $TUN_IFACE is up. Launching app."
    break
  fi

  # If OpenVPN process died, show logs and exit
  if [ -f "$PID_FILE" ] && ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[entrypoint] OpenVPN exited unexpectedly. Last 100 log lines:" >&2
    tail -n 100 "$LOG_FILE" >&2 || true
    exit 1
  fi

  TRIES=$((TRIES+1))
  if [ $TRIES -ge 30 ]; then
    echo "[entrypoint] TUN device not available after waiting. Last 100 OpenVPN log lines:" >&2
    tail -n 100 "$LOG_FILE" >&2 || true
    exit 1
  fi
  echo "[entrypoint] Waiting for tun interface... ($TRIES)"
  sleep 1
done

exec python -m src.main
