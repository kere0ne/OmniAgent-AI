import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function Models() {
  const [providers, setProviders] = useState<any[]>([]);
  const [form, setForm] = useState({ name: "", kind: "ollama", base_url: "http://localhost:11434/v1", api_key: "", default_model: "" });
  const [test, setTest] = useState<{ [id: string]: string }>({});
  const [error, setError] = useState("");

  const load = () => api("/models").then(setProviders).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function add() {
    try { await api("/models", { method: "POST", body: form }); setForm({ ...form, name: "", api_key: "", default_model: "" }); load(); }
    catch (e: any) { setError(e.message); }
  }
  async function testOne(id: number) {
    setTest({ ...test, [id]: "testing..." });
    try {
      const r = await api(`/models/${id}/test`, { method: "POST" });
      setTest({ ...test, [id]: r.ok ? `connected: ${(r.models || []).slice(0, 8).join(", ") || "no models listed"}` : r.error });
    } catch (e: any) { setTest({ ...test, [id]: e.message }); }
  }

  return (
    <div className="p-5 max-w-3xl overflow-y-auto h-full">
      <h2 className="text-base font-semibold mb-1">Model providers</h2>
      <p className="muted text-[13px] mb-4">
        Free-first: point the platform at a local Ollama server (ollama.com), a llama.cpp server, or any
        OpenAI-compatible endpoint. API keys are stored server-side and never sent to the browser.
      </p>
      {error && <div className="text-xs mb-3" style={{ color: "#f87171" }}>{error}</div>}
      <div className="space-y-2 mb-6">
        {providers.map((p) => (
          <div key={p.id} className="panel p-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium">{p.name}</span>
                <span className="muted text-xs ml-2">{p.kind} · {p.base_url || "built-in"} · model: {p.default_model || "not set"}</span>
                {p.is_default && <span className="ml-2 text-xs text-green-400">default</span>}
              </div>
              <div className="flex gap-1.5">
                <button className="btn" onClick={() => testOne(p.id)}>Test</button>
                {!p.is_default && <button className="btn" onClick={async () => { await api(`/models/${p.id}/set-default`, { method: "POST" }); load(); }}>Set default</button>}
                <button className="btn btn-danger" onClick={async () => { await api(`/models/${p.id}`, { method: "DELETE" }); load(); }}>Delete</button>
              </div>
            </div>
            {test[p.id] && <div className="text-xs mt-2 muted mono">{test[p.id]}</div>}
          </div>
        ))}
        {providers.length === 0 && (
          <div className="panel p-4 text-[13px] muted">
            No providers yet. To run a free local model: install Ollama, run <span className="mono">ollama serve</span> and
            <span className="mono"> ollama pull llama3.2</span>, then add it below with the default address.
          </div>
        )}
      </div>
      <div className="panel p-4">
        <div className="font-medium mb-3">Add provider</div>
        <div className="grid grid-cols-2 gap-2">
          <input className="input" placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="input" value={form.kind} onChange={(e) => {
            const kind = e.target.value;
            setForm({ ...form, kind, base_url: kind === "ollama" ? "http://localhost:11434/v1" : form.base_url });
          }}>
            <option value="ollama">Ollama (local, free)</option>
            <option value="openai_compatible">OpenAI-compatible endpoint</option>
            <option value="mock">Mock (offline testing)</option>
          </select>
          <input className="input" placeholder="base url" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
          <input className="input" placeholder="model (e.g. llama3.2)" value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} />
          <input className="input" placeholder="api key (optional, stored server-side)" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
          <div />
        </div>
        <button className="btn btn-primary mt-3" onClick={add} disabled={!form.name.trim()}>Add provider</button>
      </div>
    </div>
  );
}
