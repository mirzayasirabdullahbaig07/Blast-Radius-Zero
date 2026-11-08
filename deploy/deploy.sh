#!/usr/bin/env bash
# One-shot deploy on a fresh Ubuntu 22.04/24.04 Vultr Cloud Compute instance.
# Usage:  sudo bash deploy/deploy.sh
set -euo pipefail

APP_DIR=/opt/blast-radius-zero
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then echo "Run as root: sudo bash deploy/deploy.sh"; exit 1; fi

echo "==> Installing packages"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io nginx python3-venv python3-pip rsync ufw
systemctl enable --now docker

echo "==> Creating service user"
id brz &>/dev/null || useradd -r -m -s /usr/sbin/nologin brz
usermod -aG docker brz

echo "==> Copying app to $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a --delete --exclude .venv --exclude .env --exclude .git "$SRC_DIR/" "$APP_DIR/"
[ -f "$APP_DIR/.env" ] || cp "$APP_DIR/.env.example" "$APP_DIR/.env"

echo "==> Building sandbox image"
docker build -t brz-sandbox:latest "$APP_DIR/sandbox"

echo "==> Python environment"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements-api.txt"
chown -R brz:brz "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> systemd + nginx"
cp "$APP_DIR/deploy/blast-radius-zero.service" /etc/systemd/system/
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/blast-radius-zero
ln -sf /etc/nginx/sites-available/blast-radius-zero /etc/nginx/sites-enabled/blast-radius-zero
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
systemctl daemon-reload
systemctl enable --now blast-radius-zero

echo "==> Firewall"
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable

echo
echo "Done. Now put your key in $APP_DIR/.env (VULTR_INFERENCE_API_KEY) and run:"
echo "  sudo systemctl restart blast-radius-zero"
echo "Open: http://$(curl -s ifconfig.me 2>/dev/null || echo YOUR_VM_IP)/"
