# Least privilege for the backend (AppRole "dtr-backend"):
# read the JWT key, read/rotate the field keys, nothing else in Vault.
path "secret/data/dtr/jwt" {
  capabilities = ["read"]
}

path "secret/data/dtr/field-keys" {
  capabilities = ["read", "create", "update"]
}

path "secret/metadata/dtr/field-keys" {
  capabilities = ["read"]
}

# Destroy old KV versions that still contain retired keys.
path "secret/destroy/dtr/field-keys" {
  capabilities = ["update"]
}
