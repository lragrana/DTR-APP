# DTR-APP (Timetrack) – Team SoloSecure, MO-IT153 A4101

Daily Time Record web app (React + Flask + MongoDB, Docker Compose) used for IAS 2.

## Milestone 2 controls
- **C1 – MFA (TOTP) for admin and supervisor accounts** – `backend/routes/mfa.py`, `backend/routes/auth.py`,
  `backend/app.py` (MFA-pending token gate), `frontend/src/components/MfaStep.jsx`.
- **C2 – Managed encryption keys with rotation (HashiCorp Vault)** – `backend/keyring.py`, `backend/security.py`,
  `backend/routes/admin.py` (`/api/admin/keys`, `/api/admin/keys/rotate`), `vault/`, `scripts/vault-init.sh`.

Baseline before the changes: git tag `m2-baseline` (rollback: `git checkout m2-baseline`, restore the database
archive and the old `.env` from the offline backup).

## Run locally
```sh
sh scripts/generate-env.sh          # creates .env with random secrets (first time only)
docker compose up -d vault          # start Vault
sh scripts/vault-init.sh            # first time only: init + unseal Vault, move keys out of .env
docker compose up -d --build        # start mongo, backend, web
# after any restart of the Vault container:
sh scripts/vault-unseal.sh && docker compose restart backend
```
Open https://localhost (self-signed certificate). Admin and supervisor accounts are asked to set up an
authenticator app on their first login.

Secrets (`.env`, `secrets/`) are never committed.
