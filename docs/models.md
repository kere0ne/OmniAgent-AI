# Model configuration

## Free local models (recommended)

**Ollama**

```bash
curl -fsSL https://ollama.com/install.sh | sh   # or download from ollama.com
ollama serve
ollama pull llama3.2          # general
ollama pull qwen2.5-coder     # coding-focused
```

In OmniAgent: Models -> Add provider -> Ollama. Base URL defaults to
`http://localhost:11434/v1` (Ollama's OpenAI-compatible endpoint). Test, then Add.

**llama.cpp**

```bash
./llama-server -m model.gguf --port 8080
```

Add an "OpenAI-compatible endpoint" provider with base URL `http://localhost:8080/v1`.

**Other hosts**: vLLM, LM Studio, Together, Groq, OpenAI all speak the same protocol:
set the base URL and (where needed) an API key, stored server-side only.

## Provider settings

Per-provider JSON settings: `temperature`, `max_tokens`, `context_length`.
Streaming is used for chat; the agent loop uses complete responses with tool calls.

## Choosing a default

The first provider you add becomes the default; change it with "Set default".
Chat and agent runs use the default provider's `default_model`.

## Mock provider

Kind `mock` runs a deterministic scripted provider for tests and offline UI work.
It never pretends to be a real model and clearly labels its output.
