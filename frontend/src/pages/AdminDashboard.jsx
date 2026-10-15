import { useEffect, useState } from "react";
import { api } from "../api.js";
import Records from "../components/Records.jsx";

// Sensitive actions ask for the password again (re-authentication).
function ConfirmPassword({ title, onConfirm, onCancel }) {
  const [password, setPassword] = useState("");
  return (
    <form className="card confirm" onSubmit={(e) => { e.preventDefault(); onConfirm(password); }}>
      <p>{title}</p>
      <label>Your password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required autoFocus /></label>
      <button type="submit" className="danger">Confirm</button>
      <button type="button" className="link" onClick={onCancel}>Cancel</button>
    </form>
  );
}

export default function AdminDashboard({ user }) {
  const isAdmin = user.role === "admin";
  const [records, setRecords] = useState([]);
  const [users, setUsers] = useState([]);
  const [pending, setPending] = useState(null);
  const [msg, setMsg] = useState("");
  const [keys, setKeys] = useState(null);

  const load = () => {
    api("/attendance").then(setRecords).catch((e) => setMsg(e.message));
    if (isAdmin) api("/admin/users").then(setUsers).catch((e) => setMsg(e.message));
    if (isAdmin) api("/admin/keys").then(setKeys).catch((e) => setMsg(e.message));
  };
  useEffect(() => { load(); }, []);

  async function confirm(password) {
    const p = pending;
    setPending(null);
    try {
      const data = p.type === "delete"
        ? await api(`/attendance/${p.record.id}`, { method: "DELETE", body: { password } })
        : p.type === "rotate"
          ? await api("/admin/keys/rotate", { method: "POST", body: { password } })
          : await api(`/admin/users/${encodeURIComponent(p.username)}/role`, { method: "PATCH", body: { role: p.role, password } });
      setMsg(data.message);
      load();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <section>
      {pending && (
        <ConfirmPassword
          title={pending.type === "delete" ? `Delete the record of ${pending.record.username}?`
            : pending.type === "rotate" ? "Rotate the field encryption key? All encrypted data will be re-encrypted with a new key."
              : `Change ${pending.username} to ${pending.role}?`}
          onConfirm={confirm}
          onCancel={() => setPending(null)}
        />
      )}
      {msg && <p className="info">{msg}</p>}
      <h2>All attendance</h2>
      <Records records={records} showUser onDelete={isAdmin ? (record) => setPending({ type: "delete", record }) : undefined} />
      {isAdmin && (
        <>
          <h2>Users and roles</h2>
          <table>
            <thead><tr><th>User</th><th>Role</th><th>MFA</th><th>Locked</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username}>
                  <td>{u.username}</td>
                  <td>
                    <select value={u.role} disabled={u.username === user.username}
                      onChange={(e) => setPending({ type: "role", username: u.username, role: e.target.value })}>
                      <option value="intern">intern</option>
                      <option value="supervisor">supervisor</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>{u.mfa ? "on" : u.role === "intern" ? "–" : "not set up"}</td>
                  <td>{u.locked ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h2>Encryption keys (Vault)</h2>
          {keys && (
            <div className="actions">
              <span>Current key: <b>{keys.current}</b> · versions in Vault: {keys.versions.join(", ")} · encrypted values: {Object.entries(keys.encrypted_values_by_version).map(([v, n]) => `${v}=${n}`).join(", ") || "none"}</span>
              <button className="danger" onClick={() => setPending({ type: "rotate" })}>Rotate key</button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
