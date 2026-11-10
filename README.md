# DTR-APP (Timetrack) – Team SoloSecure, MO-IT153 A4101

Daily Time Record web app (React + Flask + MongoDB, Docker Compose) used for IAS 2.
Employees clock in/out; admin and supervisor accounts manage records. The project adds
two security controls on top of the base app (Milestone 2).

## Milestone 2 controls
- **C1 – MFA (TOTP) for admin and supervisor accounts** – `backend/routes/mfa.py`, `backend/routes/auth.py`,
  `backend/app.py` (MFA-pending token gate), `frontend/src/components/MfaStep.jsx`.
- **C2 – Managed encryption keys with rotation (HashiCorp Vault)** – `backend/keyring.py`, `backend/security.py`,
  `backend/routes/admin.py` (`/api/admin/keys`, `/api/admin/keys/rotate`), `vault/`, `scripts/vault-init.sh`.

Baseline before the changes: git tag `m2-baseline` (rollback: `git checkout m2-baseline`, restore the database
archive and the old `.env` from the offline backup).

## Architecture (Docker Compose services)
| Service   | Image / build        | Exposed? | Role |
|-----------|----------------------|----------|------|
| `web`     | `./frontend` (nginx) | **yes** – ports 80/443 | React UI, serves HTTPS, proxies `/api` to the backend |
| `backend` | `./backend` (Flask)  | no (internal only) | API; pulls JWT + field-encryption keys from Vault |
| `mongo`   | `mongo:8.0`          | no (internal only) | Database, on a private network |
| `vault`   | `hashicorp/vault`    | no (internal only) | Stores the JWT key and field-encryption keys (C2) |

Only `web` is reachable from your machine; the database and Vault sit on internal-only networks.

## Prerequisites
- **Docker Desktop** (or Docker Engine) with **Docker Compose v2** (`docker compose`, not `docker-compose`).
- A POSIX shell (macOS/Linux Terminal, or Git Bash / WSL on Windows) with **`openssl`** and **`python3`**
  on the host — the setup scripts use them.
- A web browser.

## Quick start (one command)
First time, from the project root, just run:

```sh
sh scripts/setup.sh     # creates .env, inits + unseals Vault, builds and starts everything
```

Every time after that (or after a reboot):

```sh
sh scripts/start.sh     # starts the stack, unseals Vault, restarts the backend
```

Then open **https://localhost**. Prefer to run the steps by hand? They're spelled out below.

## How to run (first time, step by step)
Run everything from the project root (`DTR-APP/`):

```sh
# 1. Create .env with strong random secrets (DB passwords, JWT key, admin login).
#    Prints the generated admin password location. Does NOT overwrite an existing .env.
sh scripts/generate-env.sh

# 2. Start Vault on its own first.
docker compose up -d vault

# 3. One-time Vault setup: initialise + unseal, create the AppRole the backend uses,
#    move the JWT and field-encryption keys out of .env and into Vault.
#    Writes the unseal key + AppRole credentials into ./secrets/ (keep these offline, never commit).
sh scripts/vault-init.sh

# 4. Build and start the rest of the stack (mongo, backend, web).
docker compose up -d --build
```

Then open **https://localhost** and accept the self-signed-certificate warning (the cert is generated
at build time, so browsers won't trust it — that's expected for local dev).

**Admin login:** username `admin`; the password was generated into `.env` (line `ADMIN_PASSWORD=`).
On first login, admin/supervisor accounts are prompted to set up an authenticator app (Google Authenticator,
Authy, etc.) — scan the QR code, then enter the 6-digit code to finish signing in (that's Control 1).

## Starting it again later (after a reboot / `docker compose down`)
Vault **seals itself every time its container restarts**, so after any restart you must unseal it,
then restart the backend so it can read the keys again:

```sh
docker compose up -d                       # bring the stack back up
sh scripts/vault-unseal.sh                 # unseal Vault with the saved key
docker compose restart backend             # backend re-reads keys from the now-unsealed Vault
```

(`scripts/vault-unseal.sh` prints `Sealed  false` once Vault is open.)

## Stopping / resetting
```sh
docker compose down            # stop containers, keep data (mongo + vault volumes persist)
docker compose down -v         # stop AND delete all data/volumes — full reset
```
A full reset (`-v`) wipes Vault too, so you'd re-run step 3 (`vault-init.sh`) afterward.

## Troubleshooting
- **Backend keeps restarting / 500 on login after a reboot** → Vault is sealed. Run the unseal + restart
  steps above.
- **`.env already exists – not overwriting`** → that's intentional; delete `.env` only if you want fresh
  secrets (you'll then need to reset Vault too).
- **Port 80/443 already in use** → stop whatever is using them, or change the `web` port mapping in
  `docker-compose.yaml`.

## Security notes
Secrets (`.env`, `secrets/`) are generated locally and are **never committed** (see `.gitignore`).
Turnstile uses Cloudflare's always-pass **test** keys for local dev; swap in real keys for production.
