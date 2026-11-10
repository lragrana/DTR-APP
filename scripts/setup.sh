#!/bin/sh
# One-command FIRST-TIME setup for a fresh clone.
# Does everything: secrets -> Vault init -> build -> start -> unseal.
# Safe to re-run: each step is skipped if it is already done.
set -e
cd "$(dirname "$0")/.."

echo "==> 1/5  Creating .env (random secrets + admin login)"
[ -f .env ] && echo "    .env already exists, keeping it" || sh scripts/generate-env.sh

echo "==> 2/5  Starting Vault"
docker compose up -d vault
# wait until the Vault container answers
i=0; until docker compose exec -T vault vault status >/dev/null 2>&1 || [ $i -ge 15 ]; do i=$((i+1)); sleep 1; done

echo "==> 3/5  Initialising Vault (one time) and moving keys out of .env"
[ -f secrets/vault-init.json ] && echo "    Vault already initialised, skipping" || sh scripts/vault-init.sh

echo "==> 4/5  Building and starting the app (mongo, backend, web)"
docker compose up -d --build

echo "==> 5/5  Unsealing Vault and restarting the backend"
sh scripts/vault-unseal.sh || true
docker compose restart backend

echo ""
echo "Done. Open  https://localhost  (accept the self-signed certificate)."
echo "Admin login: username 'admin', password is the ADMIN_PASSWORD line in .env"
echo "Next time, just run:  sh scripts/start.sh"
