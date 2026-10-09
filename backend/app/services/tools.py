"""Tool registry. Every tool has a JSON schema, a permission class, a timeout,
and returns structured output. New tools register via register()."""
import os
from . import workspaces
from .executor import run
from ..config import CFG

REGISTRY: dict = {}

def register(name, description, schema, perm, fn, timeout=None):
    REGISTRY[name] = {"name": name, "description": description, "schema": schema,
                      "perm": perm, "fn": fn, "timeout": timeout}
    return REGISTRY[name]

def ctx_for(user_id, workspace_id, db=None):
    return {"user_id": user_id, "workspace_id": workspace_id}

MUTATING = {"write_file", "run_command", "git_commit", "git_push"}

def _ensure(ws_ctx):
    return workspaces.ensure_ws(ws_ctx["user_id"], ws_ctx["workspace_id"])

def t_list_files(args, ctx):
    root = _ensure(ctx)
    rel = args.get("path", ".")
    base = workspaces.resolve_safe(ctx["user_id"], ctx["workspace_id"], rel)
    if base.is_file(): base = base.parent
    tree = workspaces.list_tree(base)
    limit = int(args.get("limit", 400))
    return {"ok": True, "entries": tree[:limit], "total": len(tree)}

def t_read_file(args, ctx):
    p = workspaces.resolve_safe(ctx["user_id"], ctx["workspace_id"], args["path"])
    if not p.exists(): return {"ok": False, "error": "file not found"}
    if p.is_dir(): return {"ok": False, "error": "path is a directory"}
    if p.stat().st_size > 1_000_000: return {"ok": False, "error": "file too large for tool read (>1MB); use run_command"}
    return {"ok": True, "path": args["path"], "content": p.read_text(errors="replace")}

def t_write_file(args, ctx):
    p = workspaces.resolve_safe(ctx["user_id"], ctx["workspace_id"], args["path"])
    used = workspaces.ws_disk_usage(ctx["user_id"], ctx["workspace_id"])
    if used + len(args["content"].encode()) > CFG.WORKSPACE_QUOTA_MB * 1024 * 1024:
        return {"ok": False, "error": "workspace disk quota exceeded"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"])
    return {"ok": True, "path": args["path"], "bytes": len(args["content"].encode())}

def t_run_command(args, ctx):
    root = _ensure(ctx)
    timeout = min(int(args.get("timeout", CFG.EXEC_TIMEOUT_DEFAULT)), CFG.EXEC_TIMEOUT_MAX)
    r = run(args["command"], str(root), timeout=timeout, cpu=CFG.EXEC_CPU_SECONDS, mem_mb=CFG.EXEC_MEM_MB)
    r["ok"] = r["exit_code"] == 0
    return r

def t_search_files(args, ctx):
    root = _ensure(ctx)
    hits = workspaces.find_files(root, args.get("pattern", "*"))
    needle = args.get("contains")
    results = []
    for h in hits[:100]:
        p = root / h
        try:
            if p.is_file() and p.stat().st_size < 512_000:
                if needle and needle not in p.read_text(errors="replace"): continue
                results.append(h)
        except OSError: continue
    return {"ok": True, "matches": results}

def t_finish(args, ctx):
    return {"ok": True, "summary": args.get("summary", ""), "unfinished": args.get("unfinished", "")}

register("list_files", "List files and directories in the workspace",
         {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}},
         "read", t_list_files)
register("read_file", "Read a text file from the workspace",
         {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
         "read", t_read_file)
register("write_file", "Create or overwrite a file in the workspace",
         {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
         "write", t_write_file)
register("run_command", "Execute a shell command in the workspace sandbox",
         {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
         "exec", t_run_command, timeout=CFG.EXEC_TIMEOUT_MAX)
register("search_files", "Find files by glob pattern, optionally filtering by contained text",
         {"type": "object", "properties": {"pattern": {"type": "string"}, "contains": {"type": "string"}}},
         "read", t_search_files)
register("finish", "Finish the task. Call when the goal is met or blocked.",
         {"type": "object", "properties": {"summary": {"type": "string"}, "unfinished": {"type": "string"}}},
         "read", t_finish)

def tool_definitions(names=None):
    names = names or list(REGISTRY)
    return [{"type": "function", "function": {"name": n, "description": REGISTRY[n]["description"],
             "parameters": REGISTRY[n]["schema"]}} for n in names if n in REGISTRY]

def allowed_for(user, tool_name):
    try:
        import json as _j
        perms = _j.loads(user.tool_permissions or '{}')
    except Exception:
        perms = {}
    if not perms: return True
    denies, allows = perms.get("deny", []), perms.get("allow", ["*"])
    if "*" in denies: return False
    if tool_name in denies: return False
    return "*" in allows or tool_name in allows
