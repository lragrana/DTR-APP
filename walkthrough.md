# DTR-APP — Full Walkthrough (setup → login → demo the two controls)

A step-by-step anyone can follow start to finish. **The two things we are proving:**

- **Control 1 — MFA / OTP:** a stolen password alone cannot log in. You also need the 6-digit code from a phone authenticator app.
- **Control 2 — Vault key management:** the encryption keys live in HashiCorp Vault (not in the code / `.env`), and can be rotated with **zero data loss**.

---

## 0. What you need (once)

- **Docker Desktop** (with Docker Compose v2)
- **Git**
- A terminal with **`openssl`** and **`python3`** (Mac: built-in; run `xcode-select --install` once for python3. Windows: use WSL2 / Ubuntu.)
- A **web browser**
- A **phone with an authenticator app** (Google Authenticator, Microsoft Authenticator, or Authy)

---

## 1. Get the code

```sh
git clone https://github.com/lragrana/DTR-APP.git
cd DTR-APP
```

> On this Mac it is already here: `/Users/andrian/Desktop/Cheska-Net/IAS2/DTR-APP`
> Open it in VS Code with: `code /Users/andrian/Desktop/Cheska-Net/IAS2/DTR-APP`

---

## 2. Set it up — one command (first time only)

```sh
sh scripts/setup.sh
```

This creates `.env` (random secrets + admin login), initialises and unseals Vault, moves the keys out of `.env` into Vault, then builds and starts everything. Safe to re-run.

**Every time after that (or after a reboot):**

```sh
sh scripts/start.sh
```

(Vault seals itself on every restart — `start.sh` unseals it and restarts the backend.)

---

## 3. Open the app

Go to **https://localhost**. Chrome shows **"Your connection is not private"** → click **Advanced** → **Proceed to localhost**.

> That warning is just our local **self-signed certificate** — HTTPS is working, the browser just doesn't trust a self-signed issuer. Not a flaw.

---

## 4. Get the admin password

It lives in the project's **`.env`** file, line **`ADMIN_PASSWORD=`**. From inside the `DTR-APP` folder:

```sh
grep ADMIN_PASSWORD .env
```

- Every laptop generates **its own** password when `setup.sh` runs.
- On **this Mac**, it is also written in **`secrets/DEMO-LOGIN.txt`**.

---

## 5. Log in — this is Control 1 (MFA / OTP) ⭐

1. Enter username **`admin`** and the password from step 4, click **Log in**.
2. The app does **NOT** let you straight in — it shows **"Two-step verification."**
   → **This is Control 1 working: a correct password alone is not enough.**
3. **First login only — set up the authenticator:**
   - The app shows a **QR code**. Open your phone's authenticator app → **scan the QR** (or choose "Enter a setup key" and type the key shown on screen).
   - The app then shows **8 one-time backup codes** — save them somewhere safe (they are only used if you lose your phone; each works once).
4. **Every login (including now):** open the authenticator app on your phone, read the **current 6-digit code** (it changes every 30 seconds), type it into the box, click **Verify**.
5. You're in. 🎉

**Prove it's real (optional but strong):** log out, log back in, and type a **wrong** 6-digit code → it's rejected. Five wrong codes → the account **locks**.

> **Where the OTP comes from:** your phone's authenticator app generates the 6-digit code from the secret the QR gave it, in sync with the server. It is **never** sent by SMS or email. The 8 backup codes are only the fallback for a lost phone.

---

## 6. Demo Control 2 (Vault key rotation) ⭐

Once you're logged in as admin, scroll to the **"Encryption keys (Vault)"** panel. It shows something like:

```
Current key: v1 · versions in Vault: v1 · encrypted values: v1=8
```

That line means the app's field-encryption key lives **in Vault** (not in `.env`), and `v1` is the current version.

1. Click **Rotate key**.
2. The app asks for your **password again** (re-authentication — rotating keys is a sensitive action).
3. Enter the admin password → **Confirm**.
4. **Result:** a banner **"Encryption key rotated to v2"**, the panel updates to the new version, **every stored value is re-encrypted**, and **all records still display correctly — zero data loss.** The old key version is retired.

**What this proves:** the encryption keys are centrally managed in Vault and can be rotated at will without losing data — and because they're no longer in `.env`, a leaked config file can't expose them.

**(Optional) Show the keys really aren't in `.env`:**

```sh
grep -E 'FIELD_ENCRYPTION_KEY|JWT_SECRET_KEY' .env     # → nothing; vault-init moved them into Vault
```

---

## 7. The two-line summary to say out loud

- **Control 1 (MFA/OTP):** "A stolen admin password is useless now — login also needs the 6-digit code from the authenticator on our phone, and guessing it is rate-limited and locked out."
- **Control 2 (Vault):** "The encryption keys moved out of the code into Vault, where they're versioned and rotatable — we just rotated the key live and every record still read back perfectly."

---

## Where the code lives (for a code walk-through)

If a panelist says "show us the code," open these files (`code /Users/andrian/Desktop/Cheska-Net/IAS2/DTR-APP`):

**Control 1 — MFA / OTP**
- `backend/routes/mfa.py` — MFA enrolment (QR), confirm, and verify endpoints
- `backend/routes/auth.py` — login; after the password it issues the 5-minute **MFA-pending token** and checks the code
- `backend/security.py` — password hashing, field-encryption of the TOTP secret, `roles_required`, `reauthenticate`
- `backend/audit.py` — writes every MFA event (success / fail / lock) to the audit log
- `frontend/src/components/Login.jsx` — the login form + CAPTCHA
- `frontend/src/components/MfaStep.jsx` — the **QR setup + 6-digit code** screen

**Control 2 — Vault key management**
- `backend/keyring.py` — the **Vault client**: AppRole login + `key_for(version)` that fetches keys from Vault
- `backend/security.py` — `encrypt_field` / `decrypt_field` (tags each value with its key version, pulls the key from the keyring)
- `backend/routes/admin.py` — `/api/admin/keys` (status) and `/api/admin/keys/rotate` (**the Rotate key action**, with re-auth)
- `vault/config/vault.hcl` + `vault/policies/dtr-backend.hcl` — Vault server config + the backend's **least-privilege policy**
- `scripts/vault-init.sh` — one-time: moves the keys **out of `.env` into Vault**, creates the AppRole
- `scripts/vault-unseal.sh` — unseals Vault after a restart
- `frontend/src/pages/AdminDashboard.jsx` — the **"Encryption keys (Vault)" panel + Rotate key** button

---

## Restart / stop / reset

```sh
sh scripts/start.sh            # start again (handles the Vault unseal)
docker compose down            # stop, keep all data
docker compose down -v         # stop AND wipe all data (then re-run: sh scripts/setup.sh)
```

## ⚠️ Do NOT show on screen
The **`secrets/`** folder, the **`.env`** file, or **`secrets/DEMO-LOGIN.txt`** — they hold live keys and passwords.

## Quick troubleshooting
- **500 error / won't log in after a reboot** → Vault is sealed → run `sh scripts/start.sh`.
- **"Invalid code"** → the OTP changes every 30s, so read a fresh one; make sure the phone's clock is correct.
- **Port 80/443 already in use** → quit whatever's using them, or change the `web` ports in `docker-compose.yaml`.
