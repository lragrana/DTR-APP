#!/bin/sh
# Vault starts sealed after every restart. Unseal it with the key from vault-init.json.
set -e
cd "$(dirname "$0")/.."
UNSEAL=$(python3 -c "import json;print(json.load(open('secrets/vault-init.json'))['unseal_keys_b64'][0])")
docker compose exec -T -e VAULT_ADDR=http://127.0.0.1:8200 vault vault operator unseal "$UNSEAL" | grep -E "Sealed"
