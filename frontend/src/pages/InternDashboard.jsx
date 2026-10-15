import { useEffect, useState } from "react";
import { api } from "../api.js";
import Records from "../components/Records.jsx";

export default function InternDashboard() {
  const [records, setRecords] = useState([]);
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => api("/attendance/me").then(setRecords).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);

  async function act(path, body) {
    setMsg("");
    try {
      const data = await api(path, { method: "POST", body });
      setMsg(data.message);
      setNotes("");
      load();
    } catch (e) {
      setMsg(e.message);
    }
  }

  const open = records.some((r) => !r.check_out);
  return (
    <section>
      <h2>My attendance</h2>
      <div className="actions">
        <input placeholder="Notes (optional)" maxLength={200} value={notes} onChange={(e) => setNotes(e.target.value)} disabled={open} />
        <button onClick={() => act("/attendance/check-in", { notes: notes || undefined })} disabled={open}>Check in</button>
        <button onClick={() => act("/attendance/check-out")} disabled={!open}>Check out</button>
      </div>
      {msg && <p className="info">{msg}</p>}
      <Records records={records} />
    </section>
  );
}
