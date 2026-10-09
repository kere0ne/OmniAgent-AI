import React, { useEffect, useState } from "react";
import { api } from "../api";
import type { ActiveWS } from "../App";

export default function GitView({ active }: { active: ActiveWS | null }) {
  const [hasToken, setHasToken] = useState<boolean | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [cloneUrl, setCloneUrl] = useState("");
  const [commitMsg, setCommitMsg] = useState("");
  const [out, setOut] = useState("");
  const [error, setError] = useState("");
  const wid = active?.workspaceId;

  useEffect(() => { api("/workspaces/git/credential" as any).catch(() => {}); }, []);
  useEffect(() => {
    if (wid) api(`/workspaces/${wid}/git/credential`).then((r) => setHasToken(r.has_token)).catch((e) => setError(e.message));
  }, [wid]);

  if (!wid) return <div className="p-6 muted">Open a workspace from the Projects page to use Git.</div>;

  async function call(path: string, body?: any) {
    setError(""); setOut("");
    try {
      const r = await api(`/workspaces/${wid}/git/${path}`, { method: "POST", body });
      setOut(typeof r === "object" ? (r.output || r.stdout || r.stderr || JSON.stringify(r)) : String(r));
    } catch (e: any) { setError(e.message); }
  }

  return (
    <div className="p-5 max-w-3xl overflow-y-auto h-full">
      <h2 className="text-base font-semibold mb-1">Git & GitHub</h2>
      <p className="muted text-[13px] mb-4">Workspace: <span className="mono">{active!.name}</span></p>
      {error && <div className="text-xs mb-3" style={{ color: "#f87171" }}>{error}</div>}
      <div className="panel p-4 mb-4">
        <div className="font-medium mb-2">GitHub token</div>
        {hasToken ? (
          <div className="text-[13px]">A token is saved (server-side, never shown). <button className="muted hover:underline" onClick={async () => { await call("credential", { token: "" }); setHasToken(false); }}>Remove</button></div>
        ) : (
          <div className="flex gap-2">
            <input className="input" placeholder="GitHub fine-grained PAT (repo scope)" type="password" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} />
            <button className="btn" onClick={async () => { await call("credential", { token: tokenInput }); setTokenInput(""); setHasToken(true); }}>Save</button>
          </div>
        )}
      </div>
      <div className="panel p-4 mb-4">
        <div className="font-medium mb-2">Clone repository into this workspace</div>
        <div className="flex gap-2">
          <input className="input" placeholder="https://github.com/user/repo.git" value={cloneUrl} onChange={(e) => setCloneUrl(e.target.value)} />
          <button className="btn btn-primary" onClick={() => call("clone", { url: cloneUrl })}>Clone</button>
        </div>
      </div>
      <div className="panel p-4 mb-4 space-y-2">
        <div className="font-medium mb-1">Repository actions</div>
        <div className="flex gap-2 flex-wrap">
          <button className="btn" onClick={() => call("exec", { subcommand: "status" })}>Status</button>
          <button className="btn" onClick={() => call("exec", { subcommand: "log --oneline -15" })}>Log</button>
          <button className="btn" onClick={() => call("exec", { subcommand: "branch" })}>Branches</button>
          <button className="btn" onClick={() => call("diff")}>Diff</button>
        </div>
        <div className="flex gap-2 mt-2">
          <input className="input" placeholder="commit message" value={commitMsg} onChange={(e) => setCommitMsg(e.target.value)} />
          <button className="btn" disabled={!commitMsg.trim()} onClick={() => call("commit", { message: commitMsg })}>Commit all changes</button>
        </div>
        <button className="btn btn-primary mt-2" disabled={!hasToken}
                onClick={() => { if (confirm("Push to the remote? This publishes your commits.")) call("push"); }}>
          Push (requires saved token)
        </button>
      </div>
      {out && <pre className="panel p-3 mono text-xs whitespace-pre-wrap overflow-x-auto">{out.slice(0, 8000)}</pre>}
    </div>
  );
}
