# Synapse OS Network + AI Runtime

Synapse OS continues to use the Linux kernel and NetworkManager for hardware networking. Synapse Flow v2 adds its own application-level network capability model on top.

Programs have no network permission by default. Network execution requires both `--net` and explicit `--allow-host` grants. The runtime validates HTTP/HTTPS URLs, re-validates redirect targets, caps response/request sizes, applies timeouts, and keeps API keys in environment variables rather than source or bytecode.

`ai_chat(endpoint, model, prompt, api_key_env)` targets OpenAI-compatible chat-completions APIs. This makes local or remote AI providers interchangeable at the language level while keeping the transport explicit and testable.

COSMOS localhost services can be granted by hostname/IP when needed, e.g. `--allow-host 127.0.0.1`. Existing Synapse/COSMOS port probing remains independent from the v2 network permission system.
