import json, time
from sqlalchemy import (Column, Integer, String, Text, DateTime, Boolean, ForeignKey, LargeBinary)
from sqlalchemy.sql import func
from .db import Base

def _j(v): return json.dumps(v or {})

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    pw_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    tool_permissions = Column(Text, default='{"allow": ["*"]}')  # JSON list or {"allow": [...], "deny": [...]}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    image = Column(String(120), default="python:default")  # runtime image tag
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    title = Column(String(200), default="New chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant | system | tool
    content = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AgentTask(Base):
    __tablename__ = "agent_tasks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=True)
    goal = Column(Text, nullable=False)
    role = Column(String(40), default="engineer")
    require_approval = Column(Boolean, default=False)
    status = Column(String(24), default="queued")  # queued|running|awaiting_approval|complete|failed|cancelled
    steps = Column(Text, default="[]")   # JSON event ledger (checkpoints)
    result = Column(Text, default="")
    pending_tool = Column(Text, default="")  # JSON of the tool call awaiting approval
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def events(self):
        try: return json.loads(self.steps or "[]")
        except Exception: return []

    def append_event(self, ev):
        ev["t"] = round(time.time(), 3)
        evs = self.events(); evs.append(ev)
        self.steps = json.dumps(evs[-400:])

class ModelProvider(Base):
    __tablename__ = "model_providers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    kind = Column(String(30), nullable=False, default="openai_compatible")  # openai_compatible | ollama | mock
    base_url = Column(String(300), default="")
    api_key = Column(String(300), default="")   # server-side only; never serialized to the API
    default_model = Column(String(120), default="")
    settings = Column(Text, default='{"temperature":0.2,"max_tokens":2048}')
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class GitCredential(Base):
    __tablename__ = "git_credentials"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    github_token = Column(String(300), default="")  # server-side only

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(80), nullable=False)
    detail = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
