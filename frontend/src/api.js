// All calls go to the same origin over HTTPS (nginx proxies /api to the backend).
const TOKEN_KEY = "dtr_token";

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t) => sessionStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && token && !path.startsWith("/auth/login")) {
    clearToken();
    window.dispatchEvent(new Event("dtr:logout"));
  }
  if (!res.ok) {
    const detail = data.requirements ? `: ${data.requirements.join(", ")}` : "";
    throw new Error((data.error || `Request failed (${res.status})`) + detail);
  }
  return data;
}
