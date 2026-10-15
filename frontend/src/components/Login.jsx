import { useCallback, useState } from "react";
import { api, setToken } from "../api.js";
import Captcha from "./Captcha.jsx";
import MfaStep from "./MfaStep.jsx";

export default function Login({ onLogin, onShowSignup }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [error, setError] = useState("");
  const [mfa, setMfa] = useState(null);
  const onToken = useCallback((t) => setCaptcha(t), []);

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: { username, password, captcha_token: captcha },
      });
      if (data.mfa_required) { setMfa(data); return; }
      setToken(data.access_token);
      onLogin();
    } catch (err) {
      setError(err.message);
    }
  }

  if (mfa) {
    return <MfaStep mfa={mfa} onDone={onLogin} onCancel={() => { setMfa(null); setPassword(""); }} />;
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Log in</h2>
      <label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /></label>
      <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
      <Captcha onToken={onToken} />
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={!captcha}>Log in</button>
      <p>No account? <button type="button" className="link" onClick={onShowSignup}>Sign up</button></p>
    </form>
  );
}
