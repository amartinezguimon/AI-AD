#!/usr/bin/env bash
# Install the VisionMetrics edge agent as a systemd service on a Linux edge box.
#
# Usage (run as root from the repo root):
#   sudo bash visionmetrics/edge/deploy/install_linux.sh /opt/visionmetrics
#
# Assumes: the repo is at the given INSTALL_DIR, a venv exists at
# INSTALL_DIR/venv with requirements installed, and a device.yaml exists at
# visionmetrics/edge/config/device.yaml.
set -euo pipefail

INSTALL_DIR="${1:-/opt/visionmetrics}"
SERVICE_USER="${SERVICE_USER:-visionmetrics}"
UNIT_NAME="visionmetrics-agent"
CONFIG_PATH="$INSTALL_DIR/visionmetrics/edge/config/device.yaml"
PYTHON_BIN="$INSTALL_DIR/venv/bin/python"

echo "==> Installing $UNIT_NAME from $INSTALL_DIR"

[[ -x "$PYTHON_BIN" ]] || { echo "ERROR: venv python not found at $PYTHON_BIN"; exit 1; }
[[ -f "$CONFIG_PATH" ]] || { echo "ERROR: device.yaml not found at $CONFIG_PATH (copy device.example.yaml and edit it)"; exit 1; }

# Create a dedicated unprivileged service user if it doesn't exist.
if ! id "$SERVICE_USER" &>/dev/null; then
  echo "==> Creating service user '$SERVICE_USER'"
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi
# The agent needs to read the repo and (for USB cams) the video group.
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
usermod -aG video "$SERVICE_USER" || true

# Render the unit file with the real paths.
UNIT_SRC="$INSTALL_DIR/visionmetrics/edge/deploy/$UNIT_NAME.service"
UNIT_DST="/etc/systemd/system/$UNIT_NAME.service"
sed \
  -e "s|^User=.*|User=$SERVICE_USER|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" \
  -e "s|^ExecStart=.*|ExecStart=$PYTHON_BIN -m visionmetrics.edge.agent.service --config $CONFIG_PATH|" \
  "$UNIT_SRC" > "$UNIT_DST"

echo "==> Reloading systemd and enabling $UNIT_NAME"
systemctl daemon-reload
systemctl enable --now "$UNIT_NAME"

echo "==> Done. Useful commands:"
echo "    systemctl status $UNIT_NAME"
echo "    journalctl -u $UNIT_NAME -f"
