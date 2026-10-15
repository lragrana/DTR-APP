#!/bin/sh
# Creates .env with strong random secrets. Never commit .env.
set -e
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env already exists – not overwriting"; exit 1; fi
rand() { openssl rand -hex "$1"; }
cat > .env <<ENV
MONGO_ROOT_USERNAME=dtr_root
MONGO_ROOT_PASSWORD=$(rand 24)
APP_DB_USER=dtr_app
APP_DB_PASSWORD=$(rand 24)
JWT_SECRET_KEY=$(rand 32)
FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)
# Cloudflare Turnstile TEST keys (always pass). Replace with real keys for production.
TURNSTILE_SITEKEY=1x00000000000000000000AA
TURNSTILE_SECRET=1x0000000000000000000000000000000AA
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Adm-$(rand 8)-X9!
ENV
chmod 600 .env
echo ".env created (admin password is inside)"
