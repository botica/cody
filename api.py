"""Ollama API streaming and response handling (native API)."""

import json
import uuid
import requests

from tools import get_tools_schema
import printer
import config

OLLAMA_URL = "http://localhost:11434/api/chat"

# Re-export config values (use config.MODEL directly for dynamic switching)
SHOW_REASONING = config.SHOW_REASONING


def get_model():
    """Get current model (supports runtime switching)."""
    return config.MODEL


def check_config():
    """Check if Ollama is reachable."""
    try:
        requests.get("http://localhost:11434/", timeout=2)
        return True
    except requests.exceptions.RequestException:
        printer.error("can't connect to Ollama - is it running? (ollama serve)")
        return False


def stream_completion(conversation: list, session) -> tuple[str, list[dict], dict | None]:
    payload = {
        "model": config.MODEL,
        "messages": conversation,
        "tools": get_tools_schema(),
        "stream": True
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120)
    except requests.exceptions.RequestException as e:
        printer.error(f"connection failed: {e}")
        return "", [], None

    with response:
        response.encoding = 'utf-8'
        if response.status_code != 200:
            _handle_api_error(response)
            return "", [], None

        current_text = ""
        tool_calls = []
        prompt_tokens = 0
        completion_tokens = 0
        at_line_start = True

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Get message content
            message = data.get("message", {})
            content = message.get("content", "")

            if content:
                printer.stream_content(content)
                current_text += content
                at_line_start = content.endswith('\n')

            # Check for tool calls
            if message.get("tool_calls"):
                for tc in message["tool_calls"]:
                    func = tc.get("function", {})
                    tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "name": func.get("name", ""),
                        "arguments": json.dumps(func.get("arguments", {}))
                    })

            # Final message has done=true and token counts
            if data.get("done"):
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)

    # Final cleanup
    if current_text and not at_line_start:
        print(printer.COLORS['reset'], end='', flush=True)
        printer.newline()

    # Update usage
    if prompt_tokens or completion_tokens:
        session.token_usage["input"] += prompt_tokens
        session.token_usage["output"] += completion_tokens
        session.turn_tokens_in += prompt_tokens
        session.turn_tokens_out += completion_tokens
        printer.usage(prompt_tokens, completion_tokens, None,
                      session.turn_tokens_in, session.turn_tokens_out, None,
                      session.token_usage['input'], session.token_usage['output'], None)

    return current_text, tool_calls, None


def _handle_api_error(response):
    error_msg = f"API Error {response.status_code}"
    try:
        error_data = response.json()
        if "error" in error_data:
            error_msg += f": {error_data['error']}"
    except Exception:
        error_msg += f": {response.text[:200]}"
    printer.error(error_msg)
