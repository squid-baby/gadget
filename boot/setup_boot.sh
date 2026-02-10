#!/bin/bash
# LEELOO Boot Setup Script
# Run this once on the Pi to configure clean boot experience

set -e

echo "=========================================="
echo "LEELOO Boot Setup"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup_boot.sh)"
    exit 1
fi

LEELOO_DIR="/home/pi/leeloo-ui"

# 1. Update cmdline.txt to hide boot text
echo "[1/5] Configuring boot parameters..."

CMDLINE="/boot/firmware/cmdline.txt"
if [ ! -f "$CMDLINE" ]; then
    CMDLINE="/boot/cmdline.txt"
fi

# Backup original
cp "$CMDLINE" "${CMDLINE}.backup"

# Read current cmdline
CURRENT=$(cat "$CMDLINE")

# Add quiet splash parameters if not present
if [[ ! "$CURRENT" =~ "quiet" ]]; then
    CURRENT="$CURRENT quiet"
fi

if [[ ! "$CURRENT" =~ "splash" ]]; then
    CURRENT="$CURRENT splash"
fi

if [[ ! "$CURRENT" =~ "loglevel=0" ]]; then
    CURRENT="$CURRENT loglevel=0"
fi

if [[ ! "$CURRENT" =~ "vt.global_cursor_default=0" ]]; then
    CURRENT="$CURRENT vt.global_cursor_default=0"
fi

# Make sure console is NOT on fb1 (our LCD)
# Change fbcon=map:01 to fbcon=map:0 if present
CURRENT=$(echo "$CURRENT" | sed 's/fbcon=map:01/fbcon=map:0/g')

# Ensure fbcon=map:0 is set
if [[ ! "$CURRENT" =~ "fbcon=map:0" ]]; then
    CURRENT="$CURRENT fbcon=map:0"
fi

# Write updated cmdline (must be single line)
echo "$CURRENT" | tr -s ' ' > "$CMDLINE"
echo "  Updated $CMDLINE"

# 2. Disable rainbow splash
echo "[2/5] Disabling rainbow splash..."

CONFIG="/boot/firmware/config.txt"
if [ ! -f "$CONFIG" ]; then
    CONFIG="/boot/config.txt"
fi

# Add disable_splash if not present
if ! grep -q "disable_splash=1" "$CONFIG"; then
    echo "disable_splash=1" >> "$CONFIG"
    echo "  Added disable_splash=1"
else
    echo "  Already disabled"
fi

# 3. Install splash service (runs very early)
echo "[3/5] Installing splash service..."

cp "$LEELOO_DIR/boot/leeloo-splash.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable leeloo-splash.service
echo "  Enabled leeloo-splash.service"

# 4. Install main LEELOO service
echo "[4/5] Installing main LEELOO service..."

cp "$LEELOO_DIR/boot/leeloo.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable leeloo.service

# Disable old gadget service if it exists
systemctl disable gadget.service 2>/dev/null || true
systemctl stop gadget.service 2>/dev/null || true

echo "  Enabled leeloo.service"

# 5. Set permissions
echo "[5/5] Setting permissions..."

chown -R pi:pi "$LEELOO_DIR"
chmod +x "$LEELOO_DIR/boot/leeloo_splash.py"
chmod +x "$LEELOO_DIR/leeloo_boot.py"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Changes made:"
echo "  - Boot text hidden (quiet splash loglevel=0)"
echo "  - Rainbow splash disabled"
echo "  - Console kept off LCD (fbcon=map:0)"
echo "  - Cursor hidden (vt.global_cursor_default=0)"
echo "  - leeloo-splash.service enabled (early splash)"
echo "  - leeloo.service enabled (main UI)"
echo ""
echo "Reboot to see the new boot experience:"
echo "  sudo reboot"
echo ""
