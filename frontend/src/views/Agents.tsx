import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ActiveWS } from "../App";

const ROLES = ["team", "architect", "engineer", "debugger", "reviewer", "tester", "researcher", "devops", "docs"];

export default function Agents({ active }: { active: ActiveWS | null }) {
  const [tasks, setTasks] = useState<any[]>([]);
  const [goal, setGoal] = useState("");
  const [role, setRole] = useState("engineer");
  const [approval, setApproval] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<any | null>(null);
  const pollRef = useRef<any>(null);

  const load = () => api("/agents").then(setTasks).catch(() => {});
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!open || !["running", "queued", "awaiting_approval"].includes(open.status)) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    pollRef.current = setInterval(async () => {
      try { setOpen(await api(`/agents/${open.id}`)); load(); } catch {}
    }, 1500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open?.id, open?.status]);

  async function run() {
    if (!goal.trim()) return;
    setError("");
    try {
      const r = await api("/agents/run", {
        method: "POST",
        body: { goal, role, require_approval: approval, workspace_id: active?.workspaceId || null },
      });
      setGoal("");
      setOpen(await api(`/agents/${r.id}`));
      load();
    } catch (e: any) { setError(e.message); }
  }

  async function approveTask(approved: boolean) {
    try { setOpen(await api(`/agents/${open.id}/approve`, { method: "POST", body: { approved } })); } catch (e: any) { setError(e.message); }
  }
  async function cancel() {
    try { setOpen(await api(`/agents/${open.id}/cancel`, { method: "POST" })); load(); } catch (e: any) { setError(e.message); }
  }

  const badge: Record<string, string> = {
    complete: "text-green-400", failed: "text-red-400", running: "text-blue-400",
    awaiting_approval: "text-yellow-400", cancelled: "text-gray-400", queued: "text-gray-400",
  };

  return (
    <div className="flex h-full">
      <div className="w-72 shrink-0 border-r p-4 overflow-y-auto" style={{ borderColor: "#1c2333" }}>
        <h2 className="text-base font-semibold mb-1">Agent runs</h2>
        <p className="muted text-xs mb-3">{active ? `Workspace: ${active.name}` : "No workspace attached (agent runs without file access)."}</p>
        <textarea className="input mb-2" rows={4} placeholder="Describe the task, e.g. 'Build a Flask API with tests and run them'"
                  value={goal} onChange={(e) => setGoal(e.target.value)} />
        <div className="flex gap-2 mb-2">
          <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 text-xs muted mb-3">
          <input type="checkbox" checked={approval} onChange={(e) => setApproval(e.target.checked)} />
          Ask approval before writes and commands
        </label>
        <button className="btn btn-primary w-full" onClick={run} disabled={!goal.trim()}>Run agent</button>
        {error && <div className="text-xs mt-2" style={{ color: "#f87171" }}>{error}</div>}
        <div className="mt-4 space-y-1">
          {tasks.map((t) => (
            <button key={t.id} className={"nav-item " + (open?.id === t.id ? "active" : "")} onClick={async () => setOpen(await api(`/agents/${t.id}`))}>
              <span className="truncate">#{t.id} {t.role}: {t.goal}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {!open && <div className="muted">Select a run or start a new one.</div>}
        {open && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <span className="font-medium">#{open.id} {open.role}</span>
                <span className={"ml-3 text-xs " + (badge[open.status] || "")}>{open.status}</span>
              </div>
              <div className="flex gap-2">
                {open.status === "awaiting_approval" && (
                  <>
                    <button className="btn btn-primary" onClick={() => approveTask(true)}>Approve</button>
                    <button className="btn btn-danger" onClick={() => approveTask(false)}>Reject</button>
                  </>
                )}
                {["running", "queued", "awaiting_approval"].includes(open.status) && (
                  <button className="btn btn-danger" onClick={cancel}>Cancel</button>
                )}
              </div>
            </div>
            <div className="panel p-3 mb-3 text-[13px] whitespace-pre-wrap">{open.goal}</div>
            {open.pending_tool && (
              <div className="panel p-3 mb-3" style={{ borderColor: "#a16207" }}>
                <div className="text-xs mb-1" style={{ color: "#fbbf24" }}>Waiting for approval</div>
                <div className="mono text-xs whitespace-pre-wrap">{open.pending_tool.name} {JSON.stringify(open.pending_tool.arguments, null, 2)}</div>
              </div>
            )}
            <div className="space-y-2">
              {open.events.map((e: any, i: number) => (
                <div key={i} className="panel p-3 text-[13px]">
                  {e.type === "assistant" && <div className="whitespace-pre-wrap">{e.text}</div>}
                  {e.type === "tool" && (
                    <div>
                      <span className="mono text-xs" style={{ color: "#22d3ee" }}>{e.tool}</span>
                      <pre className="mono text-xs mt-1 overflow-x-auto whitespace-pre-wrap muted">{JSON.stringify(e.result, null, 2).slice(0, 2000)}</pre>
                    </div>
                  )}
                  {e.type === "approval_needed" && <div className="text-xs" style={{ color: "#fbbf24" }}>approval needed: {e.tool}</div>}
                  {e.type === "error" && <div className="text-xs" style={{ color: "#f87171" }}>{e.error}</div>}
                  {e.type === "start" && <div className="muted text-xs">Started</div>}
                  {e.type === "cancelled" && <div className="muted text-xs">Cancelled by user</div>}
                  {e.type === "step_limit" && <div className="muted text-xs">Reached step limit</div>}
                </div>
              ))}
            </div>
            {open.result && (
              <div className="panel p-3 mt-3 text-[13px] whitespace-pre-wrap">{open.result}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
