# C2 – HashiCorp Vault server for the DTR app (stand-in for a cloud KMS).
# Reachable only on the internal "vault-net" Docker network (no published port).
storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  # Traffic stays on an internal Docker network that only the backend joins.
  tls_disable = true
}

api_addr      = "http://vault:8200"
disable_mlock = true
ui            = false
