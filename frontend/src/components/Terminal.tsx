import React, { useEffect, useRef, useState } from "react";
import { api, apiOrigin, getToken } from "../api";

export default function Terminal({ workspaceId }: { workspaceId: number }) {
  const [connected, setConnected] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let alive = true;
    (async () => {
      try {
        const s = await api(`/workspaces/${workspaceId}/terminal/open`, { method: "POST" });
        if (!alive) return;
        const origin = new URL(apiOrigin());
        const proto = origin.protocol === "https:" ? "wss" : "ws";
        ws = new WebSocket(`${proto}://${origin.host}/api/ws/terminal/${s.session_id}?token=${getToken()}`);
        wsRef.current = ws;
        ws.onopen = () => setConnected(true);
        ws.onmessage = (e) => {
          const m = JSON.parse(e.data);
          if (m.type === "output") setLines((l) => [...l.slice(-500), m.output]);
          if (m.type === "exit" && m.exit_code !== 0 && m.exit_code !== null)
            setLines((l) => [...l, `[exit ${m.exit_code}]`]);
          if (m.type === "error") setLines((l) => [...l, `[${m.message}]`]);
          if (m.type === "ready") setLines([`session ready in ${m.cwd}`]);
        };
        ws.onclose = () => setConnected(false);
      } catch (e: any) {
        setLines([`terminal error: ${e.message}`]);
      }
    })();
    return () => { alive = false; wsRef.current?.close(); };
  }, [workspaceId]);

  useEffect(() => { boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight }); }, [lines]);

  function run() {
    const cmd = input;
    if (!cmd || !wsRef.current) return;
    setLines((l) => [...l, `$ ${cmd}`]);
    wsRef.current.send(JSON.stringify({ command: cmd }));
    setInput("");
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-2 py-1 text-xs border-b" style={{ borderColor: "#1c2333" }}>
        <span className={"w-2 h-2 rounded-full inline-block " + (connected ? "bg-green-500" : "bg-red-500")} />
        sandbox terminal {connected ? "(connected)" : "(disconnected)"}
      </div>
      <div ref={boxRef} className="flex-1 overflow-y-auto mono text-[12.5px] px-2 py-1 whitespace-pre-wrap" style={{ background: "#070a12" }}>
        {lines.join("")}
      </div>
      <div className="flex gap-1 p-1.5 border-t" style={{ borderColor: "#1c2333" }}>
        <span className="mono text-xs self-center px-1" style={{ color: "#22d3ee" }}>$</span>
        <input className="input mono text-[12.5px]" value={input}
               onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") run(); }}
               placeholder="command runs in this workspace's sandbox..." />
        <button className="btn" onClick={run}>Run</button>
      </div>
    </div>
  );
}
