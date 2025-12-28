# Cody

AI coding agent CLI using OpenRouter API with tool use capabilities.

## Running

```bash
python agent.py
```

Requires `OPENROUTER_API_KEY` environment variable.

## Project Structure

- `agent.py` - Main entry point, REPL loop, agent execution
- `api.py` - OpenRouter streaming, token usage tracking
- `config.py` - Model selection, pricing, session state, system prompt
- `tools/` - Tool registry and implementations
  - `__init__.py` - Tool decorator, schema generation, execution
  - `filesystem.py` - File read/write/edit
  - `search.py` - File/content search
  - `web.py` - Web fetch/search
  - `shell.py` - Bash command execution

## Key Patterns

- Tools registered via `@tool` decorator with JSON schema params
- Dangerous tools require user confirmation (y/n/! for auto-confirm turn)
- Streaming output with reasoning support (deepseek-r1, etc.)
- Session tracks cwd, token usage, conversation history

## Changing Models

Edit `MODEL` in `config.py`. Add pricing to `MODEL_PRICING` dict for cost tracking.
