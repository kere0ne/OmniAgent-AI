import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Conversation, Message, ModelProvider, Project, Workspace
from ..services.providers import provider_from_row, ProviderError
from ..deps import current_user, limiter

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatIn(BaseModel):
    content: str
    conversation_id: int | None = None
    project_id: int | None = None
    workspace_id: int | None = None

def _default_provider(db, user_id):
    return (db.query(ModelProvider).filter_by(user_id=user_id, is_default=True).first()
            or db.query(ModelProvider).filter_by(user_id=user_id).first())

@router.get("/conversations")
def list_conversations(user=Depends(current_user), db: Session = Depends(get_db)):
    cs = db.query(Conversation).filter_by(user_id=user.id).order_by(Conversation.id.desc()).limit(100).all()
    return [{"id": c.id, "title": c.title, "project_id": c.project_id} for c in cs]

@router.get("/conversations/{cid}/messages")
def messages(cid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.user_id != user.id: raise HTTPException(404, "conversation not found")
    ms = db.query(Message).filter_by(conversation_id=cid).order_by(Message.id).all()
    return [{"id": m.id, "role": m.role, "content": m.content} for m in ms]

@router.post("/stream")
def stream(body: ChatIn, user=Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"user{user.id}")
    if not body.content.strip(): raise HTTPException(400, "empty message")
    conv = None
    if body.conversation_id:
        conv = db.get(Conversation, body.conversation_id)
        if not conv or conv.user_id != user.id: raise HTTPException(404, "conversation not found")
    if not conv:
        conv = Conversation(user_id=user.id, project_id=body.project_id,
                            title=body.content.strip()[:60])
        db.add(conv); db.commit(); db.refresh(conv)
    db.add(Message(conversation_id=conv.id, role="user", content=body.content)); db.commit()

    prow = _default_provider(db, user.id)
    if not prow:
        raise HTTPException(400, "No AI model configured. Add one on the Models page (e.g. Ollama at http://localhost:11434/v1) or select the built-in mock provider for offline testing.")
    provider = provider_from_row(prow)
    model = prow.default_model or "llama3"
    settings = {"temperature": 0.2, "max_tokens": 4096, "context_length": 8192}

    history = db.query(Message).filter_by(conversation_id=conv.id).order_by(Message.id).all()
    msgs = []
    context_bits = []
    if body.workspace_id:
        w = db.get(Workspace, body.workspace_id)
        if w:
            from ..models import Project
            p = db.get(Project, w.project_id)
            if p and p.user_id == user.id:
                from ..services import workspaces
                root = workspaces.ws_root(user.id, w.id)
                tree = workspaces.list_tree(root)[:80]
                context_bits.append(f"You are attached to workspace '{w.name}'. Files:\n" + json.dumps(tree))
    sys_prompt = "You are OmniAgent AI, a capable AI software engineering assistant. Be direct, correct, and concrete. If a workspace is attached, use its real file listing."
    if context_bits: sys_prompt += "\n\n" + "\n".join(context_bits)
    msgs.append({"role": "system", "content": sys_prompt})
    for m in history[-30:]:
        if m.role in ("user", "assistant"):
            msgs.append({"role": m.role, "content": m.content})

    conv_id = conv.id

    def gen():
        full = []
        try:
            import httpx
            with httpx.Client(timeout=300) as client:
                payload = {"model": model, "messages": msgs, "stream": True,
                           "temperature": settings["temperature"], "max_tokens": settings["max_tokens"]}
                headers = {"Authorization": f"Bearer {getattr(provider, 'api_key', 'not-needed')}"}
                with client.stream("POST", f"{provider.base_url}/chat/completions", json=payload, headers=headers) as r:
                    if r.status_code >= 400:
                        err = r.read().decode(errors="replace")[:300]
                        yield f"data: {json.dumps({'error': f'provider error {r.status_code}: {err}'})}\n\n"
                        return
                    for line in r.iter_lines():
                        if not line.startswith("data:"): continue
                        data = line[5:].strip()
                        if data == "[DONE]": break
                        try: chunk = json.loads(data)
                        except Exception: continue
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                        if delta:
                            full.append(delta)
                            yield f"data: {json.dumps({'delta': delta, 'conversation_id': conv_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'provider unreachable: {e}'})}\n\n"
            return
        text = "".join(full)
        s = SessionLocal()
        try:
            s.add(Message(conversation_id=conv_id, role="assistant", content=text)); s.commit()
        finally:
            s.close()
        yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

from ..db import SessionLocal  # noqa: E402
