"""C2 – Managed encryption keys with rotation (enhancement of R-002).

The AES-256 field keys and the JWT signing secret live in HashiCorp Vault (KV v2), not in .env.
The backend logs in with AppRole; the role_id / secret_id are mounted as Docker secrets.

Vault secret  secret/dtr/field-keys = {"current": "v2", "v1": "<base64 key>", "v2": "<base64 key>"}
Vault secret  secret/dtr/jwt        = {"signing_key": "<hex>"}

Every ciphertext starts with its key version ("v1:", "v2:"), so old data stays readable after a rotation
until it is re-encrypted, and a retired key version is removed from Vault.
"""
import base64
import os
import threading

import hvac

FIELD_KEYS_PATH = "dtr/field-keys"
JWT_PATH = "dtr/jwt"
MOUNT = "secret"

_lock = threading.Lock()
_keys = {}        # version -> 32-byte key
_current = None   # version used for new encryptions
_client = None


def _read_secret_file(name):
    path = os.path.join(os.environ.get("VAULT_SECRETS_DIR", "/run/secrets"), name)
    with open(path) as f:
        return f.read().strip()


def _vault():
    """AppRole login. The token is kept in memory only and renewed by logging in again when needed."""
    global _client
    if _client is not None and _client.is_authenticated():
        return _client
    addr = os.environ.get("VAULT_ADDR")
    if not addr:
        raise RuntimeError("VAULT_ADDR is not set: encryption keys must come from Vault")
    client = hvac.Client(url=addr, timeout=5)
    client.auth.approle.login(role_id=_read_secret_file("vault_role_id"),
                              secret_id=_read_secret_file("vault_secret_id"))
    _client = client
    return client


def _parse(data):
    current = data.get("current")
    keys = {}
    for version, value in data.items():
        if version == "current":
            continue
        key = base64.b64decode(value)
        if len(key) != 32:
            raise RuntimeError(f"Field key {version} is not 32 bytes")
        keys[version] = key
    if current not in keys:
        raise RuntimeError("The current field key version is missing in Vault")
    return current, keys


def load():
    """Fetch the key ring from Vault. Called at startup (fail closed: no Vault = no app)."""
    global _current, _keys
    client = _vault()
    data = client.secrets.kv.v2.read_secret_version(path=FIELD_KEYS_PATH, mount_point=MOUNT,
                                                    raise_on_deleted_version=True)["data"]["data"]
    current, keys = _parse(data)
    with _lock:
        _current, _keys = current, keys
    return current


def jwt_signing_key():
    data = _vault().secrets.kv.v2.read_secret_version(path=JWT_PATH, mount_point=MOUNT,
                                                      raise_on_deleted_version=True)["data"]["data"]
    return data["signing_key"]


def current_key():
    with _lock:
        if _current is None:
            raise RuntimeError("Key ring not loaded")
        return _current, _keys[_current]


def key_for(version):
    with _lock:
        key = _keys.get(version)
    if key is None:
        # The key may have been added by a rotation in another process: reload once.
        load()
        with _lock:
            key = _keys.get(version)
    if key is None:
        raise RuntimeError(f"Unknown or retired field key version: {version}")
    return key


def status():
    with _lock:
        return {"current": _current, "versions": sorted(_keys, key=lambda v: int(v[1:]))}


def add_new_version():
    """Rotation step 1: create a new random key version in Vault and make it current."""
    client = _vault()
    data = client.secrets.kv.v2.read_secret_version(path=FIELD_KEYS_PATH, mount_point=MOUNT,
                                                    raise_on_deleted_version=True)["data"]["data"]
    _, keys = _parse(data)
    new_version = f"v{max(int(v[1:]) for v in keys) + 1}"
    data = dict(data)
    data[new_version] = base64.b64encode(os.urandom(32)).decode()
    data["current"] = new_version
    client.secrets.kv.v2.create_or_update_secret(path=FIELD_KEYS_PATH, secret=data, mount_point=MOUNT)
    load()
    return new_version


def retire_versions(keep):
    """Rotation step 3: remove every key version except `keep` (after all data was re-encrypted)."""
    client = _vault()
    data = client.secrets.kv.v2.read_secret_version(path=FIELD_KEYS_PATH, mount_point=MOUNT,
                                                    raise_on_deleted_version=True)["data"]["data"]
    retired = [v for v in data if v not in ("current", keep)]
    new_data = {"current": keep, keep: data[keep]}
    client.secrets.kv.v2.create_or_update_secret(path=FIELD_KEYS_PATH, secret=new_data, mount_point=MOUNT)
    # Old KV versions still hold the retired keys: destroy them so they cannot be read back.
    meta = client.secrets.kv.v2.read_secret_metadata(path=FIELD_KEYS_PATH, mount_point=MOUNT)["data"]
    old = [int(v) for v, info in meta["versions"].items()
           if int(v) < meta["current_version"] and not info.get("destroyed")]
    if old:
        client.secrets.kv.v2.destroy_secret_versions(path=FIELD_KEYS_PATH, versions=old, mount_point=MOUNT)
    load()
    return retired
