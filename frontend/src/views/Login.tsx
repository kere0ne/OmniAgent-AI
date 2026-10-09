import React, { useState } from "react";
import { api } from "../api";

export default function Login({ onDone }: { onDone: (t: string, u: string) => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const r = await api(`/auth/${mode}`, { method: "POST", body: { username, password } });
      onDone(r.token, r.username);
    } catch (e: any) {
      setErr(e.message || "failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="h-full flex items-center justify-center" style={{ background: "#0b0e14" }}>
      <form onSubmit={submit} className="panel p-7 w-[360px]">
        <div className="text-lg font-semibold mb-1">OmniAgent AI</div>
        <div className="muted mb-5 text-[13px]">Your autonomous AI development workspace.</div>
        <label className="block text-xs muted mb-1">Username</label>
        <input className="input mb-3" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label className="block text-xs muted mb-1">Password (8+ characters)</label>
        <input className="input mb-4" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {err && <div className="text-xs mb-3" style={{ color: "#f87171" }}>{err}</div>}
        <button className="btn btn-primary w-full" disabled={busy || !username || password.length < 8}>
          {mode === "register" ? "Create account" : "Sign in"}
        </button>
        <div className="mt-4 text-xs muted text-center cursor-pointer hover:underline"
             onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "register" ? "Already have an account? Sign in" : "Need an account? Register"}
        </div>
      </form>
    </div>
  );
}
