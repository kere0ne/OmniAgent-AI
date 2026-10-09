import React, { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { api } from "../api";
import Terminal from "../components/Terminal";
import type { ActiveWS } from "../App";

interface Entry { path: string; type: string; size?: number }
interface Tab { path: string; content: string; dirty: boolean }

const LANGS: Record<string, string> = {
  py: "python", js: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
  html: "html", css: "css", json: "json", md: "markdown", sh: "shell", yml: "yaml", yaml: "yaml",
  rs: "rust", go: "go", java: "java", c: "c", cpp: "cpp", h: "cpp", txt: "plaintext",
};

export default function Ide({ active }: { active: ActiveWS | null }) {
  const [files, setFiles] = useState<Entry[]>([]);
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [bottom, setBottom] = useState<"terminal" | "logs" | null>("terminal");
  const [error, setError] = useState("");
  const [newFile, setNewFile] = useState("");
  const [ws, setWs] = useState<ActiveWS | null>(active);

  const loadFiles = useCallback(() => {
    if (!ws) return;
    api(`/workspaces/${ws.workspaceId}/files`).then((r) => setFiles(r.entries)).catch((e) => setError(e.message));
  }, [ws]);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  if (!ws) {
    return <div className="p-6 muted">No workspace open. Open one from the Projects page.</div>;
  }

  async function openFile(path: string) {
    if (tabs.some((t) => t.path === path)) { setActiveTab(path); return; }
    try {
      const r = await api(`/workspaces/${ws!.workspaceId}/file?path=${encodeURIComponent(path)}`);
      setTabs((t) => [...t, { path, content: r.content, dirty: false }]);
      setActiveTab(path);
    } catch (e: any) { setError(e.message); }
  }

  async function save(path: string) {
    const tab = tabs.find((t) => t.path === path);
    if (!tab) return;
    try {
      await api(`/workspaces/${ws!.workspaceId}/file`, { method: "PUT", body: { path, content: tab.content } });
      setTabs((t) => t.map((x) => (x.path === path ? { ...x, dirty: false } : x)));
      loadFiles();
    } catch (e: any) { setError(e.message); }
  }

  function closeTab(path: string) {
    setTabs((t) => t.filter((x) => x.path !== path));
    if (activeTab === path) setActiveTab(tabs.find((t) => t.path !== path)?.path || null);
  }

  async function createFile() {
    if (!newFile.trim()) return;
    try {
      await api(`/workspaces/${ws!.workspaceId}/file`, { method: "PUT", body: { path: newFile.trim(), content: "" } });
      setNewFile(""); loadFiles();
    } catch (e: any) { setError(e.message); }
  }

  async function deleteFile(path: string) {
    if (!confirm(`Delete ${path}?`)) return;
    try { await api(`/workspaces/${ws!.workspaceId}/file?path=${encodeURIComponent(path)}`, { method: "DELETE" }); loadFiles(); closeTab(path); }
    catch (e: any) { setError(e.message); }
  }

  const tab = tabs.find((t) => t.path === activeTab);
  const lang = tab ? LANGS[tab.path.split(".").pop() || ""] || "plaintext" : "plaintext";

  return (
    <div className="flex h-full">
      <div className="w-60 shrink-0 border-r flex flex-col overflow-y-auto" style={{ borderColor: "#1c2333", background: "#0d1119" }}>
        <div className="px-3 py-2 text-xs muted">{ws.name} / files</div>
        <div className="px-2 pb-2">
          <input className="input text-xs" placeholder="new/file.py" value={newFile}
                 onChange={(e) => setNewFile(e.target.value)} onKeyDown={(e) => e.key === "Enter" && createFile()} />
        </div>
        <div className="text-[12.5px]">
          {files.map((f) => (
            <div key={f.path} className="group flex items-center justify-between px-3 py-1 hover:bg-[#141b2e] cursor-pointer"
                 style={{ paddingLeft: 12 + (f.path.split("/").length - 1) * 12 }}
                 onClick={() => f.type === "file" && openFile(f.path)}>
              <span className="truncate mono">{f.path}</span>
              <button className="opacity-0 group-hover:opacity-100 muted hover:text-red-400 px-1"
                      onClick={(e) => { e.stopPropagation(); deleteFile(f.path); }}>x</button>
            </div>
          ))}
        </div>
        <div className="mt-auto p-2 text-xs muted">
          <button className="btn w-full text-xs" onClick={loadFiles}>Refresh</button>
        </div>
      </div>
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex border-b overflow-x-auto" style={{ borderColor: "#1c2333" }}>
          {tabs.map((t) => (
            <div key={t.path}
                 className={"flex items-center gap-2 px-3 py-2 text-[12.5px] cursor-pointer border-r " + (activeTab === t.path ? "bg-[#16203a]" : "")}
                 style={{ borderColor: "#1c2333" }} onClick={() => setActiveTab(t.path)}>
              <span className="mono">{t.path.split("/").pop()}{t.dirty ? " *" : ""}</span>
              <button className="muted hover:text-white" onClick={(e) => { e.stopPropagation(); closeTab(t.path); }}>x</button>
            </div>
          ))}
          {tab && (
            <button className="btn ml-auto my-1 mr-2" onClick={() => save(tab.path)}>Save</button>
          )}
        </div>
        {error && <div className="px-3 py-1.5 text-xs" style={{ color: "#f87171", background: "#1f1418" }}>{error}</div>}
        <div className="flex-1 min-h-0">
          {tab ? (
            <Editor
              height="100%"
              theme="vs-dark"
              language={lang}
              value={tab.content}
              onChange={(v) => setTabs((t) => t.map((x) => (x.path === tab.path ? { ...x, content: v || "", dirty: true } : x)))}
              options={{ fontSize: 13, minimap: { enabled: false }, automaticLayout: true, tabSize: 4, wordWrap: "on" }}
            />
          ) : (
            <div className="muted p-6 text-sm">Open a file from the tree, or create one. Upload zips from Projects or with the agent.</div>
          )}
        </div>
        <div className="border-t" style={{ borderColor: "#1c2333", height: bottom ? 220 : 34 }}>
          <div className="flex gap-2 px-2 py-1.5 text-xs border-b" style={{ borderColor: "#1c2333" }}>
            <button className={bottom === "terminal" ? "text-white" : "muted"} onClick={() => setBottom(bottom === "terminal" ? null : "terminal")}>Terminal</button>
          </div>
          {bottom === "terminal" && <Terminal workspaceId={ws.workspaceId} />}
        </div>
      </div>
    </div>
  );
}
