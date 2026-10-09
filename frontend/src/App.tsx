import React, { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import Login from "./views/Login";
import Chat from "./views/Chat";
import Projects from "./views/Projects";
import Ide from "./views/Ide";
import Agents from "./views/Agents";
import Models from "./views/Models";
import GitView from "./views/GitView";

type View = "chat" | "projects" | "ide" | "agents" | "models" | "github";

export interface ActiveWS { projectId: number; workspaceId: number; name: string }

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [view, setView] = useState<View>("chat");
  const [username, setUsername] = useState("");
  const [active, setActive] = useState<ActiveWS | null>(null);

  useEffect(() => {
    const h = () => { setAuthed(!!getToken()); };
    window.addEventListener("omni-logout", h);
    return () => window.removeEventListener("omni-logout", h);
  }, []);

  useEffect(() => {
    if (authed) api("/auth/me").then((u) => setUsername(u.username)).catch(() => setAuthed(false));
  }, [authed]);

  if (!authed) {
    return <Login onDone={(t: string, u: string) => { setToken(t); setUsername(u); setAuthed(true); }} />;
  }

  const nav: [View, string][] = [
    ["chat", "Chat"], ["projects", "Projects"], ["ide", "IDE"],
    ["agents", "Agents"], ["models", "Models"], ["github", "GitHub"],
  ];

  return (
    <div className="flex h-full">
      <aside className="w-52 shrink-0 border-r flex flex-col" style={{ borderColor: "#1c2333", background: "#0d1119" }}>
        <div className="px-4 py-4">
          <div className="font-semibold text-[15px]">OmniAgent AI</div>
          <div className="muted text-xs mt-0.5">autonomous dev platform</div>
        </div>
        <nav className="px-2 flex flex-col gap-0.5">
          {nav.map(([v, label]) => (
            <button key={v} className={"nav-item" + (view === v ? " active" : "")} onClick={() => setView(v)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="mt-auto px-4 py-3 text-xs muted">
          Signed in as {username}
          <button className="block mt-1 muted hover:underline" onClick={() => { setToken(""); setAuthed(false); }}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 overflow-hidden">
        {view === "chat" && <Chat active={active} />}
        {view === "projects" && <Projects onOpen={(p, w, n) => { setActive({ projectId: p, workspaceId: w, name: n }); setView("ide"); }} />}
        {view === "ide" && <Ide active={active} />}
        {view === "agents" && <Agents active={active} />}
        {view === "models" && <Models />}
        {view === "github" && <GitView active={active} />}
      </main>
    </div>
  );
}
