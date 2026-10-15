import { useCallback, useState } from "react";
import { api } from "../api.js";
import Captcha from "./Captcha.jsx";

export default function Signup({ onDone }) {
  const [form, setForm] = useState({ username: "", full_name: "", password: "" });
  const [captcha, setCaptcha] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const onToken = useCallback((t) => setCaptcha(t), []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/auth/register", { method: "POST", body: { ...form, captcha_token: captcha } });
      setOk(true);
    } catch (err) {
      setError(err.message);
    }
  }

  if (ok) {
    return (
      <div className="card">
        <p>Account created. You can now log in.</p>
        <button onClick={onDone}>Go to login</button>
      </div>
    );
  }
  return (
    <form className="card" onSubmit={submit}>
      <h2>Sign up</h2>
      <label>Username<input value={form.username} onChange={set("username")} autoComplete="username" required /></label>
      <label>Full name<input value={form.full_name} onChange={set("full_name")} autoComplete="name" /></label>
      <label>Password<input type="password" value={form.password} onChange={set("password")} autoComplete="new-password" required /></label>
      <p className="hint">At least 12 characters with upper- and lower-case letters, a number and a symbol.</p>
      <Captcha onToken={onToken} />
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={!captcha}>Create account</button>
      <p><button type="button" className="link" onClick={onDone}>Back to login</button></p>
    </form>
  );
}
