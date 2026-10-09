import React, { useEffect, useRef, useState } from "react";
import { api, streamChat } from "../api";
import type { ActiveWS } from "../App";

interface Msg { role: string; content: string }
interface Conv { id: number; title: string; project_id: number | null }

export default function Chat({ active }: { active: ActiveWS | null }) {
  const [convs, setConvs] = useState<Conv[]>([]);
  const [convId, setConvId] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api("/chat/conversations").then(setConvs).catch(() => {}); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function openConv(c: Conv) {
    setConvId(c.id);
    try { setMsgs(await api(`/chat/conversations/${c.id}/messages`)); } catch (e: any) { setError(e.message); }
  }

  async function send() {
    const content = input.trim();
    if (!content || streaming) return;
    setInput(""); setError(""); setStreaming(true);
    setMsgs((m) => [...m, { role: "user", content }, { role: "assistant", content: "" }]);
    const res = await streamChat(
      { content, conversation_id: convId, project_id: active?.projectId, workspace_id: active?.workspaceId },
      (delta) => setMsgs((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + delta };
        return copy;
      })
    );
    setStreaming(false);
    if (res.error) {
      setError(res.error);
      setMsgs((m) => m.filter((x) => x.content || x.role === "user"));
    }
    api("/chat/conversations").then((cs: Conv[]) => {
      setConvs(cs);
      const mine = cs.find((c) => c.title.startsWith(content.slice(0, 30).slice(0, 30)));
      if (!convId && cs[0]) setConvId(cs[0].id);
    }).catch(() => {});
  }

  return (
    <div className="flex h-full">
      <div className="w-56 shrink-0 border-r p-2 overflow-y-auto" style={{ borderColor: "#1c2333" }}>
        <div className="text-xs muted px-2 mb-1">Conversations</div>
        {convs.map((c) => (
          <button key={c.id} className={"nav-item" + (convId === c.id ? " active" : "")}
                  onClick={() => openConv(c)} title={c.title}>
            <span className="truncate">{c.title}</span>
          </button>
        ))}
      </div>
      <div className="flex-1 flex flex-col min-w-0">
        {active && (
          <div className="px-4 py-2 text-xs muted border-b" style={{ borderColor: "#1c2333" }}>
            Workspace context attached: {active.name}
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {msgs.length === 0 && (
            <div className="muted text-sm mt-10 text-center">
              Chat with the assistant. Attach a workspace in Projects for file context.
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={"max-w-[85%] whitespace-pre-wrap " + (m.role === "user" ? "ml-auto" : "")}>
              <div className={"rounded-lg px-3.5 py-2.5 " + (m.role === "user" ? "" : "panel")}
                   style={m.role === "user" ? { background: "#1d4ed8" } : {}}>
                {m.content || (streaming && i === msgs.length - 1 ? "..." : "")}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        {error && <div className="mx-4 mb-2 text-xs" style={{ color: "#f87171" }}>{error}</div>}
        <div className="p-3 border-t flex gap-2" style={{ borderColor: "#1c2333" }}>
          <textarea
            className="input resize-none"
            rows={2}
            placeholder="Ask anything, or describe a task..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          />
          <button className="btn btn-primary self-end" onClick={send} disabled={streaming || !input.trim()}>
            {streaming ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
