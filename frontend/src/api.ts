let token = localStorage.getItem("omni_token") || "";
export function setToken(t: string) {
  token = t;
  if (t) localStorage.setItem("omni_token", t); else localStorage.removeItem("omni_token");
}
export function getToken() { return token; }

export async function api(path: string, opts: any = {}): Promise<any> {
  const headers = { ...(opts.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  if (opts.body && typeof opts.body !== "string" && !(opts.body instanceof FormData)) {
    opts = { ...opts, body: JSON.stringify(opts.body), headers: { ...headers, "Content-Type": "application/json" } };
  } else { opts = { ...opts, headers }; }
  const r = await fetch(`/api${path}`, opts);
  if (r.status === 401) { setToken(""); window.dispatchEvent(new Event("omni-logout")); throw new Error("Signed out or session expired"); }
  const text = await r.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) throw new Error((data && data.detail) || `error ${r.status}`);
  return data;
}

export async function streamChat(body: any, onDelta: (s: string) => void): Promise<{ error?: string }> {
  const r = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!r.ok || !r.body) {
    let detail = `error ${r.status}`;
    try { detail = (await r.json()).detail || detail; } catch {}
    return { error: detail };
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const p of parts) {
      const line = p.trim();
      if (!line.startsWith("data:")) continue;
      try {
        const ev = JSON.parse(line.slice(5).trim());
        if (ev.delta) onDelta(ev.delta);
        if (ev.error) return { error: ev.error };
        if (ev.done) return {};
      } catch {}
    }
  }
  return {};
}
