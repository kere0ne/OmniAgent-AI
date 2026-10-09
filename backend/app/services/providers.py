"""Model provider abstraction. One client covers Ollama (which serves an
OpenAI-compatible endpoint at /v1), llama.cpp servers, vLLM, LM Studio, OpenAI,
Groq, Together, or any OpenAI-compatible endpoint. A MockProvider exists for
tests and offline development; it is clearly labelled and never faked as real."""
import json
import httpx

class ProviderError(Exception): pass

def _settings(raw: str) -> dict:
    try:
        s = json.loads(raw or "{}")
    except Exception:
        s = {}
    return {"temperature": float(s.get("temperature", 0.2)),
            "max_tokens": int(s.get("max_tokens", 2048)),
            "context_length": int(s.get("context_length", 8192))}

class OpenAICompatProvider:
    kind = "openai_compatible"
    def __init__(self, base_url: str, api_key: str = "", name: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "not-needed"
        self.name = name

    async def list_models(self):
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{self.base_url}/models",
                            headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
            data = r.json()
            return [m.get("id") for m in data.get("data", [])]

    async def test_connection(self):
        models = await self.list_models()
        return {"ok": True, "models": models}

    async def chat(self, messages, model, settings, tools=None):
        body = {"model": model, "messages": messages, "temperature": settings["temperature"],
                "max_tokens": settings["max_tokens"], "stream": False}
        if tools: body["tools"] = tools
        async with httpx.AsyncClient(timeout=300) as c:
            r = await c.post(f"{self.base_url}/chat/completions", json=body,
                             headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code >= 400:
                raise ProviderError(f"provider returned {r.status_code}: {r.text[:500]}")
            msg = r.json()["choices"][0]["message"]
            return msg

class OllamaProvider(OpenAICompatProvider):
    kind = "ollama"
    def __init__(self, base_url="", api_key="", name=""):
        super().__init__(base_url or "http://localhost:11434/v1", "ollama", name)

class MockProvider:
    """Deterministic provider for tests and offline dev. Scripted steps; honest about what it is."""
    kind = "mock"
    def __init__(self, script=None):
        self.script = script or []
        self.i = 0

    async def list_models(self): return ["mock-echo"]

    async def test_connection(self): return {"ok": True, "models": ["mock-echo"]}

    async def chat(self, messages, model, settings, tools=None):
        if self.i < len(self.script):
            step = self.script[self.i]; self.i += 1
            if step.get("tool"):
                return {"role": "assistant", "content": None,
                        "tool_calls": [{"id": f"call_{self.i}", "type": "function",
                                        "function": {"name": step["tool"], "arguments": json.dumps(step.get("args", {}))}}]}
            return {"role": "assistant", "content": step.get("content", "")}
        return {"role": "assistant", "content": "Mock provider: scripted steps exhausted."}

def provider_from_row(row):
    if row.kind == "ollama":
        return OllamaProvider(row.base_url, row.api_key, row.name)
    if row.kind == "mock":
        return MockProvider()
    return OpenAICompatProvider(row.base_url, row.api_key, row.name)

def build(kind: str, base_url: str = "", api_key: str = ""):
    if kind == "ollama": return OllamaProvider(base_url, api_key)
    if kind == "mock": return MockProvider()
    if kind == "openai_compatible":
        if not base_url: raise ProviderError("base_url is required for openai_compatible providers")
        return OpenAICompatProvider(base_url, api_key)
    raise ProviderError(f"unknown provider kind: {kind}")
