import React, { useEffect, useState } from "react";
import { api } from "../api";

interface WS { id: number; name: string; image: string }
interface Proj { id: number; name: string; description: string; workspaces: WS[] }

export default function Projects({ onOpen }: { onOpen: (pid: number, wid: number, name: string) => void }) {
  const [projects, setProjects] = useState<Proj[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [wsName, setWsName] = useState<{ [pid: number]: string }>({});

  const load = () => api("/projects").then(setProjects).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function create() {
    if (!name.trim()) return;
    try { await api("/projects", { method: "POST", body: { name } }); setName(""); load(); }
    catch (e: any) { setError(e.message); }
  }
  async function createWs(pid: number) {
    const n = wsName[pid] || "main";
    try { await api(`/projects/${pid}/workspaces`, { method: "POST", body: { name: n } }); load(); }
    catch (e: any) { setError(e.message); }
  }
  async function del(pid: number) {
    if (!confirm("Delete this project and all its workspace files?")) return;
    try { await api(`/projects/${pid}`, { method: "DELETE" }); load(); } catch (e: any) { setError(e.message); }
  }

  return (
    <div className="p-5 max-w-4xl overflow-y-auto h-full">
      <h2 className="text-base font-semibold mb-1">Projects</h2>
      <p className="muted text-[13px] mb-4">Each project holds isolated workspaces with their own files and terminal.</p>
      <div className="flex gap-2 mb-5 max-w-md">
        <input className="input" placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn btn-primary" onClick={create}>Create</button>
      </div>
      {error && <div className="text-xs mb-3" style={{ color: "#f87171" }}>{error}</div>}
      <div className="space-y-3">
        {projects.map((p) => (
          <div key={p.id} className="panel p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">{p.name}</div>
              <button className="btn btn-danger" onClick={() => del(p.id)}>Delete</button>
            </div>
            {p.workspaces.length === 0 && <div className="muted text-xs">No workspaces yet.</div>}
            <div className="space-y-2">
              {p.workspaces.map((w) => (
                <div key={w.id} className="flex items-center gap-2 text-[13px]">
                  <span className="mono">{w.name}</span>
                  <span className="muted text-xs">{w.image}</span>
                  <button className="btn ml-2" onClick={() => onOpen(p.id, w.id, w.name)}>Open IDE</button>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-3 max-w-xs">
              <input className="input" placeholder="workspace name" value={wsName[p.id] || ""}
                     onChange={(e) => setWsName({ ...wsName, [p.id]: e.target.value })} />
              <button className="btn" onClick={() => createWs(p.id)}>Add</button>
            </div>
          </div>
        ))}
        {projects.length === 0 && !error && <div className="muted">No projects yet. Create one above.</div>}
      </div>
    </div>
  );
}
