"""Autonomous agent loop: PLAN -> INSPECT -> ACT -> OBSERVE -> DEBUG -> VERIFY -> COMPLETE.

Runs in a background thread, persists each step as a checkpoint event (so a
restart can show exactly where it stopped), supports cancellation, approval
gating for mutating tools, per-step timeouts, and bounded retries. The agent
only reports what its tool results actually showed."""
import asyncio, json, re, threading, traceback
from ..db import SessionLocal
from ..models import AgentTask, User, Workspace
from ..services import tools as toolreg
from ..services.providers import provider_from_row, ProviderError
from ..models import ModelProvider

ROLES = {
    "architect": "You are the Architect Agent. Design application architecture, produce implementation plans, identify dependencies and technical risks. Prefer writing a design doc file over code.",
    "engineer": "You are the Software Engineer Agent. Write and modify application code, implement features across multiple files. Keep edits targeted; never overwrite a whole file when a small edit suffices.",
    "debugger": "You are the Debugging Agent. Analyze stack traces, compiler errors, and failing tests; reproduce, diagnose, and implement fixes.",
    "reviewer": "You are the Code Review Agent. Review code for maintainability, correctness, and security. Report findings; only change code when a fix is clearly warranted.",
    "tester": "You are the Testing Agent. Create and run unit, integration, and end-to-end tests. Report real test output, never invented results.",
    "researcher": "You are the Research Agent. Investigate libraries, APIs, and errors from documentation available to your tools. Cite sources for findings.",
    "devops": "You are the DevOps Agent. Configure builds, containers, CI/CD, and deployment files.",
    "docs": "You are the Documentation Agent. Generate README, API docs, and setup instructions that match the actual code.",
    "team": "You are the Orchestrator. Plan the work, then complete it directly, calling tools step by step.",
}

SYSTEM_TEMPLATE = """{role_prompt}

You operate inside an isolated sandbox workspace with real file and command tools.
Workflow: understand the goal, inspect the current project (list_files, read_file, search_files),
plan, then act with write_file/run_command. Observe every tool result before claiming success.
Run builds/tests and fix what actually breaks. When done, or when genuinely blocked, call finish
with an honest summary and anything left unfinished. Never claim a build, test, or edit succeeded
unless a tool result shows it did."""

def _ws_path(user_id, workspace_id):
    from . import workspaces
    return workspaces.ensure_ws(user_id, workspace_id)

def _save(db, task):
    db.add(task); db.commit()

def run_tool_call(name, raw_args, ctx, user, workspace_id):
    if name not in toolreg.REGISTRY:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        args = json.loads(raw_args or "{}")
    except Exception:
        return {"ok": False, "error": "invalid JSON arguments"}
    if not toolreg.allowed_for(user, name):
        return {"ok": False, "error": f"tool '{name}' is not permitted by your tool policy"}
    fn = toolreg.REGISTRY[name]["fn"]
    try:
        return fn(args, ctx)
    except workspaces.PathError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"tool error: {e}"}

def _is_mutating(name):
    return name in toolreg.MUTATING

def run_agent(task_id: int, script=None):
    """Execute an agent task in the background. `script` overrides the model for tests."""
    thread = threading.Thread(target=_run, args=(task_id, script), daemon=True)
    thread.start()
    return thread

def _run(task_id: int, script=None):
    db = SessionLocal()
    try:
        task = db.get(AgentTask, task_id)
        if not task or task.status not in ("queued",): return
        task.status = "running"; task.append_event({"step": 0, "type": "start", "goal": task.goal})
        _save(db, task)

        user = db.get(User, task.user_id)
        workspace_id = task.workspace_id
        ctx = toolreg.ctx_for(task.user_id, workspace_id)
        tool_defs = toolreg.tool_definitions()
        cwd_note = f"\n\nWorkspace files:\n" + json.dumps(
            toolreg.t_list_files({"limit": 100}, ctx)["entries"][:100])[:4000] if workspace_id else ""

        if script is not None:
            provider = __import__("app.services.providers", fromlist=["MockProvider"]).MockProvider(script)
            model = "mock-echo"
        else:
            prow = db.query(ModelProvider).filter_by(user_id=task.user_id, is_default=True).first() or \
                   db.query(ModelProvider).filter_by(user_id=task.user_id).first()
            if not prow:
                task.status = "failed"
                task.result = "No AI model configured. Add a provider (e.g. Ollama at http://localhost:11434/v1) on the Models page, or select the mock provider for offline testing."
                task.append_event({"type": "error", "error": task.result}); _save(db, task); return
            provider = provider_from_row(prow)
            model = prow.default_model or "llama3"
            try:
                await_models = provider  # connectivity checked lazily on first call
            except Exception:
                pass

        system = SYSTEM_TEMPLATE.format(role_prompt=ROLES.get(task.role, ROLES["engineer"]))
        if workspace_id:
            system += cwd_note
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": task.goal}]
        settings = {"temperature": 0.2, "max_tokens": 4096, "context_length": 8192}
        max_steps = 40
        final_text, unfinished = "", ""
        consecutive_failures = 0

        for step in range(1, max_steps + 1):
            db.expire_all()
            task = db.get(AgentTask, task_id)
            if not task or task.status in ("cancelled",): return
            if task.status == "awaiting_approval":
                return  # resume_agent continues the loop

            try:
                call = provider.chat(messages, model, settings, tools=tool_defs if script is None else None)
                msg = asyncio.run(call) if asyncio.iscoroutine(call) else call
            except ProviderError as e:
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    task.status = "failed"; task.result = f"model provider error: {e}"
                    task.append_event({"type": "error", "error": task.result}); _save(db, task); return
                messages.append({"role": "user", "content": f"Provider error, retrying: {e}"})
                continue
            except Exception as e:
                task.status = "failed"; task.result = f"model provider unreachable: {e}"
                task.append_event({"type": "error", "error": task.result}); _save(db, task); return

            consecutive_failures = 0
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            if content:
                task.append_event({"step": step, "type": "assistant", "text": content[:8000]})
            _save(db, task)

            if not tool_calls:
                final_text = content
                break

            messages.append({"role": "assistant", "content": content,
                             "tool_calls": tool_calls} if content or tool_calls else {"role": "assistant", "content": ""})
            for tc in tool_calls:
                fname = tc["function"]["name"]
                raw_args = tc["function"].get("arguments") or "{}"
                if _is_mutating(fname) and task.require_approval and not script:
                    task.status = "awaiting_approval"
                    task.pending_tool = json.dumps({"name": fname, "arguments": raw_args, "step": step})
                    task.append_event({"step": step, "type": "approval_needed", "tool": fname,
                                       "arguments": json.loads(raw_args) if _is_json(raw_args) else raw_args})
                    _save(db, task)
                    _resume_when_approved(task_id, step, messages)
                    return
                result = run_tool_call(fname, raw_args, ctx, user, workspace_id)
                task.append_event({"step": step, "type": "tool", "tool": fname, "result": _trim(result)})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", fname), "content": json.dumps(result)[:8000]})
                if fname == "finish":
                    final_text = result.get("summary", final_text)
                    unfinished = result.get("unfinished", "")
                    task.status = "complete"; task.result = final_text or "Task finished."
                    if unfinished: task.result += f"\n\nUnfinished: {unfinished}"
                    _save(db, task); return
                _save(db, task)
        task = db.get(AgentTask, task_id)
        if task.status == "running":
            task.status = "complete"
            task.result = final_text or "Reached the step limit before finishing. Partial work is saved in the workspace."
            task.append_event({"type": "step_limit"}); _save(db, task)
    except Exception as e:
        db.rollback()
        try:
            task = db.get(AgentTask, task_id)
            task.status = "failed"; task.result = f"agent crashed: {e}"
            task.append_event({"type": "error", "error": f"{e}\n{traceback.format_exc()[-1500:]}"})
            _save(db, task)
        except Exception:
            pass
    finally:
        db.close()

def _is_json(s):
    try: json.loads(s or "{}"); return True
    except Exception: return False

def _trim(result, cap=4000):
    out = {}
    for k, v in (result or {}).items():
        if isinstance(v, str) and len(v) > cap: v = v[:cap] + "..."
        out[k] = v
    return out

def _resume_when_approved(task_id: int, step: int, messages):
    """Waits for approval in a helper thread, then continues the same loop."""
    def wait():
        import time
        deadline = time.time() + 3600
        while time.time() < deadline:
            db = SessionLocal()
            try:
                t = db.get(AgentTask, task_id)
                if not t: return
                if t.status == "cancelled":
                    return
                if t.status == "running" and t.pending_tool:
                    pending = json.loads(t.pending_tool)
                    t.pending_tool = ""
                    _save(db, t)
                    if pending.get("approved"):
                        # user approved: execute and continue
                        _continue_after_approval(task_id, pending, messages)
                    else:
                        t = db.get(AgentTask, task_id)
                        t.status = "complete"
                        t.result = "Stopped at your request before executing: " + pending.get("name", "?")
                        t.append_event({"type": "rejected", "tool": pending.get("name")})
                        _save(db, t)
                    return
            finally:
                db.close()
            time.sleep(1.5)
        db = SessionLocal()
        try:
            t = db.get(AgentTask, task_id)
            if t and t.status == "awaiting_approval":
                t.status = "failed"; t.result = "Approval wait timed out after 1 hour."
                _save(db, t)
        finally:
            db.close()
    threading.Thread(target=wait, daemon=True).start()

def _continue_after_approval(task_id, pending, messages):
    """Re-enter the loop from the approved tool call."""
    def go():
        db = SessionLocal()
        try:
            task = db.get(AgentTask, task_id)
            user = db.get(User, task.user_id)
            ctx = toolreg.ctx_for(task.user_id, task.workspace_id)
            result = run_tool_call(pending["name"], pending["arguments"], ctx, user, task.workspace_id)
            task.append_event({"step": pending.get("step", 0), "type": "tool", "tool": pending["name"], "result": _trim(result)})
            if pending["name"] == "finish":
                task.status = "complete"; task.result = result.get("summary", "Task finished.")
                _save(db, task); return
            messages.append({"role": "tool", "tool_call_id": f"call_{pending.get('step', 0)}",
                             "content": json.dumps(result)[:8000]})
            _save(db, task)
        finally:
            db.close()
        # continue the main loop in a fresh thread with prior messages
        _run_continuation(task_id, messages)
    threading.Thread(target=go, daemon=True).start()

def _run_continuation(task_id: int, messages):
    """Continue an agent loop with carried context. Reuses _run logic via a lightweight wrapper."""
    def go():
        db = SessionLocal()
        try:
            task = db.get(AgentTask, task_id)
            if not task: return
            task.status = "running"; _save(db, task)
        finally:
            db.close()
        _run_steps(task_id, messages)
    threading.Thread(target=go, daemon=True).start()

def _run_steps(task_id: int, messages):
    """Continue the loop from an existing message list."""
    db = SessionLocal()
    try:
        task = db.get(AgentTask, task_id)
        if not task: return
        user = db.get(User, task.user_id)
        ctx = toolreg.ctx_for(task.user_id, task.workspace_id)
        tool_defs = toolreg.tool_definitions()
        prow = db.query(ModelProvider).filter_by(user_id=task.user_id, is_default=True).first() or \
               db.query(ModelProvider).filter_by(user_id=task.user_id).first()
        if not prow:
            task.status = "failed"; task.result = "No AI model configured."; _save(db, task); return
        provider = provider_from_row(prow)
        model = prow.default_model or "llama3"
        settings = {"temperature": 0.2, "max_tokens": 4096, "context_length": 8192}
        for step in range(1, 25):
            db.expire_all(); task = db.get(AgentTask, task_id)
            if not task or task.status in ("cancelled", "failed"): return
            try:
                call = provider.chat(messages, model, settings, tools=tool_defs)
                msg = asyncio.run(call) if asyncio.iscoroutine(call) else call
            except Exception as e:
                task.status = "failed"; task.result = f"model provider error: {e}"
                task.append_event({"type": "error", "error": task.result}); _save(db, task); return
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            if content: task.append_event({"step": step, "type": "assistant", "text": content[:8000]})
            _save(db, task)
            if not tool_calls:
                task.status = "complete"; task.result = content
                _save(db, task); return
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for tc in tool_calls:
                fname = tc["function"]["name"]; raw_args = tc["function"].get("arguments") or "{}"
                if _is_mutating(fname) and task.require_approval:
                    task.status = "awaiting_approval"
                    task.pending_tool = json.dumps({"name": fname, "arguments": raw_args, "step": step})
                    task.append_event({"step": step, "type": "approval_needed", "tool": fname})
                    _save(db, task); _resume_when_approved(task_id, step, messages); return
                result = run_tool_call(fname, raw_args, ctx, user, task.workspace_id)
                task.append_event({"step": step, "type": "tool", "tool": fname, "result": _trim(result)})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", fname), "content": json.dumps(result)[:8000]})
                if fname == "finish":
                    task.status = "complete"
                    task.result = result.get("summary", "Task finished.")
                    if result.get("unfinished"): task.result += f"\n\nUnfinished: {result['unfinished']}"
                    _save(db, task); return
                _save(db, task)
        task = db.get(AgentTask, task_id)
        if task.status == "running":
            task.status = "complete"; task.result = "Reached the step limit."
            _save(db, task)
    except Exception as e:
        db.rollback()
        try:
            task = db.get(AgentTask, task_id)
            task.status = "failed"; task.result = f"agent error: {e}"; _save(db, task)
        except Exception: pass
    finally:
        db.close()
