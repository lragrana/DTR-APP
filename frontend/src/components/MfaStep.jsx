import { useEffect, useState } from "react";
import { api, setToken } from "../api.js";

// C1: second login step for admin and supervisor accounts (TOTP, RFC 6238).
// The 5-minute "MFA pending" token from the password step is sent only to /auth/mfa/*.
export default function MfaStep({ mfa, onDone, onCancel }) {
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [backupCodes, setBackupCodes] = useState(null);
  const [error, setError] = useState("");
  const call = (path, body) => api(`/auth/mfa/${path}`, { method: "POST", body, token: mfa.mfa_token });

  useEffect(() => {
    if (!mfa.mfa_enrolled) call("setup", {}).then(setSetup).catch((e) => setError(e.message));
  }, [mfa]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await call(mfa.mfa_enrolled ? "verify" : "confirm", { code });
      setToken(data.access_token);
      if (data.backup_codes) setBackupCodes(data.backup_codes);
      else onDone();
    } catch (err) {
      setError(err.message);
      setCode("");
    }
  }

  if (backupCodes) {
    return (
      <div className="card">
        <h2>MFA is on</h2>
        <p>Save these one-time backup codes somewhere safe. Each one works once if you lose your phone. They will not be shown again.</p>
        <ul className="codes">{backupCodes.map((c) => <li key={c}><code>{c}</code></li>)}</ul>
        <button onClick={onDone}>I saved my backup codes</button>
      </div>
    );
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>{mfa.mfa_enrolled ? "Two-step verification" : "Set up two-step verification"}</h2>
      {!mfa.mfa_enrolled && (
        <>
          <p className="hint">Admin and supervisor accounts need a second factor. Scan the QR code with Google or Microsoft Authenticator, then enter the 6-digit code.</p>
          {setup && <img className="qr" src={setup.qr_svg} alt="QR code for the authenticator app" />}
          {setup && <p className="hint">Can't scan? Enter this key: <code>{setup.secret}</code></p>}
        </>
      )}
      {mfa.mfa_enrolled && <p className="hint">Enter the 6-digit code from your authenticator app, or one of your backup codes.</p>}
      <label>Code<input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={12} required autoFocus /></label>
      {error && <p className="error">{error}</p>}
      <button type="submit">Verify</button>
      <button type="button" className="link" onClick={onCancel}>Back to login</button>
    </form>
  );
}
