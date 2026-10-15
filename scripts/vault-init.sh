#!/bin/sh
# C2 one-time setup: initialise + unseal Vault, enable KV v2, audit log and AppRole,
# move FIELD_ENCRYPTION_KEY (as key version v1) and JWT_SECRET_KEY from .env into Vault,
# then remove both from .env. Run from the project folder after: docker compose up -d vault
set -e
cd "$(dirname "$0")/.."
umask 077
mkdir -p secrets
v() { docker compose exec -T -e VAULT_ADDR=http://127.0.0.1:8200 ${VTOKEN:+-e VAULT_TOKEN=$VTOKEN} vault vault "$@"; }

if [ -f secrets/vault-init.json ]; then echo "Vault already initialised (secrets/vault-init.json exists)"; exit 1; fi
. ./.env
[ -n "$FIELD_ENCRYPTION_KEY" ] && [ -n "$JWT_SECRET_KEY" ] || { echo "Keys not found in .env"; exit 1; }

v operator init -key-shares=1 -key-threshold=1 -format=json > secrets/vault-init.json
UNSEAL=$(python3 -c "import json;print(json.load(open('secrets/vault-init.json'))['unseal_keys_b64'][0])")
VTOKEN=$(python3 -c "import json;print(json.load(open('secrets/vault-init.json'))['root_token'])")
v operator unseal "$UNSEAL" >/dev/null

v secrets enable -path=secret kv-v2
v audit enable file file_path=/vault/logs/audit.log
v policy write dtr-backend - < vault/policies/dtr-backend.hcl
v auth enable approle
v write auth/approle/role/dtr-backend token_policies=dtr-backend token_ttl=1h token_max_ttl=4h secret_id_num_uses=0
v read -field=role_id auth/approle/role/dtr-backend/role-id > secrets/vault_role_id
v write -f -field=secret_id auth/approle/role/dtr-backend/secret-id > secrets/vault_secret_id

# Existing data was encrypted with the .env key, so it becomes key version v1 (no migration needed).
v kv put secret/dtr/field-keys current=v1 v1="$FIELD_ENCRYPTION_KEY" >/dev/null
v kv put secret/dtr/jwt signing_key="$JWT_SECRET_KEY" >/dev/null

# The keys no longer live in .env.
sed -i.bak -e '/^FIELD_ENCRYPTION_KEY=/d' -e '/^JWT_SECRET_KEY=/d' .env && rm -f .env.bak

# The root token is not needed day to day: revoke it (a new one can be generated with the unseal key).
v token revoke -self
python3 - <<'PY'
import json; p="secrets/vault-init.json"; d=json.load(open(p)); d["root_token"]="REVOKED"; json.dump(d, open(p, "w"), indent=2)
PY
echo "Vault ready. Keys moved out of .env. Unseal key: secrets/vault-init.json (keep offline)."
