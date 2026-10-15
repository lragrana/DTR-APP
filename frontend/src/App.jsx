import { useCallback, useEffect, useState } from "react";
import { api, clearToken, getToken } from "./api.js";
import Login from "./components/Login.jsx";
import Signup from "./components/Signup.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import InternDashboard from "./pages/InternDashboard.jsx";

const IDLE_LIMIT_MS = 15 * 60 * 1000; // log out after 15 minutes without activity

export default function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("login");
  const [notice, setNotice] = useState("");

  const loadUser = useCallback(() => {
    if (!getToken()) return;
    api("/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  const logout = useCallback(async (reason = "") => {
    try { if (getToken()) await api("/auth/logout", { method: "POST" }); } catch { /* token may already be invalid */ }
    clearToken();
    setUser(null);
    setView("login");
    setNotice(reason);
  }, []);

  useEffect(() => { loadUser(); }, [loadUser]);

  useEffect(() => {
    const onForcedLogout = () => { setUser(null); setNotice("Your session ended. Please log in again."); };
    window.addEventListener("dtr:logout", onForcedLogout);
    return () => window.removeEventListener("dtr:logout", onForcedLogout);
  }, []);

  useEffect(() => {
    if (!user) return;
    let timer;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => logout("You were logged out after 15 minutes of inactivity."), IDLE_LIMIT_MS);
    };
    const events = ["mousemove", "keydown", "click", "scroll"];
    events.forEach((ev) => window.addEventListener(ev, reset));
    reset();
    return () => { clearTimeout(timer); events.forEach((ev) => window.removeEventListener(ev, reset)); };
  }, [user, logout]);

  return (
    <main>
      <header>
        <h1>Daily Time Record</h1>
        {user && (
          <div>
            <span>{user.full_name || user.username} ({user.role})</span>
            <button className="link" onClick={() => logout()}>Log out</button>
          </div>
        )}
      </header>
      {notice && !user && <p className="info">{notice}</p>}
      {!user && view === "login" && <Login onLogin={() => { setNotice(""); loadUser(); }} onShowSignup={() => setView("signup")} />}
      {!user && view === "signup" && <Signup onDone={() => setView("login")} />}
      {user && user.role === "intern" && <InternDashboard />}
      {user && user.role !== "intern" && <AdminDashboard user={user} />}
    </main>
  );
}
