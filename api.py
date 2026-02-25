"""OpenRouter API streaming and response handling."""

import json
import uuid
import requests

from tools import get_tools_schema
import printer
import config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Re-export config values (use config.MODEL directly for dynamic switching)
MAX_TURN_COST = config.MAX_TURN_COST
SHOW_REASONING = config.SHOW_REASONING


def get_model():
    """Get current model (supports runtime switching)."""
    return config.MODEL


def check_config():
    """Check if API key is configured, prompt if missing."""
    if not config.API_KEY:
        if not config.prompt_api_key():
            return False
        # Reload the module-level constant
        config.API_KEY = config._cfg["api_key"]
    return True


def stream_completion(conversation: list, session) -> tuple[str, list[dict], dict | None]:
    headers, payload = _prepare_request_data(conversation)

    try:
        # Use a moderate read timeout so Ctrl-C can still interrupt promptly,
        # but we don't fail the request if the server takes a moment before
        # sending the first streaming chunk.
        # (connect timeout, read timeout)
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=True, timeout=(10, 60))
    except requests.exceptions.RequestException as e:
        printer.error(f"connection failed: {e}")
        return "", [], None

    with response:
        response.encoding = 'utf-8'
        if response.status_code != 200:
            _handle_api_error(response)
            return "", [], None

        # State for aggregation
        tool_calls_by_index = {}
        current_text = ""
        call_usage = None
        reasoning_details = None
        
        # State for display
        at_line_start = True
        had_reasoning = False

        for data_obj in _iter_sse_stream(response):
            if "usage" in data_obj:
                call_usage = data_obj["usage"]

            if not data_obj.get("choices"):
                continue

            choice = data_obj["choices"][0]
            delta = choice.get("delta", {})

            # 1. Update Reasoning Details (DeepSeek/Generic)
            if "reasoning_details" in choice.get("message", {}):
                reasoning_details = choice["message"]["reasoning_details"]
            elif "reasoning_details" in delta:
                reasoning_details = delta["reasoning_details"]

            # 2. Stream Reasoning Content
            reasoning = delta.get("reasoning") or delta.get("reasoning_content")
            if reasoning and SHOW_REASONING:
                printer.stream_reasoning(reasoning)
                at_line_start = reasoning.endswith('\n')
                had_reasoning = True

            # 3. Stream Main Content
            content = delta.get("content")
            if content:
                if had_reasoning:
                    if not at_line_start:
                        print(printer.COLORS['reset'], end='', flush=True)
                        printer.newline()
                    had_reasoning = False
                
                printer.stream_content(content)
                current_text += content
                at_line_start = content.endswith('\n')

            # 4. Accumulate Tool Calls
            if "tool_calls" in delta:
                _process_tool_calls(delta["tool_calls"], tool_calls_by_index)

    # Final cleanup
    if not at_line_start:
        print(printer.COLORS['reset'], end='', flush=True)
        printer.newline()

    if call_usage:
        _print_usage(call_usage, session)

    return current_text, list(tool_calls_by_index.values()), reasoning_details


def _is_anthropic_model(model: str) -> bool:
    """Return True if the model is an Anthropic/Claude model that supports prompt caching."""
    return model.startswith("anthropic/")


def _apply_anthropic_cache_control(messages: list) -> list:
    """Return a copy of messages with cache_control breakpoints injected for Anthropic models.

    Strategy (per OpenRouter docs):
      - System message: cache the entire static system prompt (it never changes).
      - Last user message: cache up to the latest user turn so the model can reuse
        the full conversation context on follow-up tool calls within the same turn.

    Only up to 4 cache_control breakpoints are allowed by Anthropic.
    """
    import copy
    messages = copy.deepcopy(messages)

    cache_control = {"type": "ephemeral"}

    # 1. Cache the system message (index 0)
    if messages and messages[0].get("role") == "system":
        content = messages[0].get("content", "")
        if isinstance(content, str):
            # Wrap in multipart array so we can attach cache_control to the text part
            messages[0]["content"] = [{"type": "text", "text": content, "cache_control": cache_control}]
        elif isinstance(content, list) and content:
            # Already multipart — attach to the last text part
            for part in reversed(content):
                if part.get("type") == "text":
                    part["cache_control"] = cache_control
                    break

    # 2. Cache the last user message (marks the boundary of stable context)
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            content = messages[i].get("content", "")
            if isinstance(content, str):
                messages[i]["content"] = [{"type": "text", "text": content, "cache_control": cache_control}]
            elif isinstance(content, list) and content:
                for part in reversed(content):
                    if part.get("type") == "text":
                        part["cache_control"] = cache_control
                        break
            break

    return messages


def _prepare_request_data(conversation: list) -> tuple[dict, dict]:
    headers = {
        "Authorization": f"Bearer {config.API_KEY}",
        "Content-Type": "application/json"
    }

    messages = conversation
    if _is_anthropic_model(config.MODEL):
        messages = _apply_anthropic_cache_control(conversation)

    payload = {
        "model": config.MODEL,
        "messages": messages,
        "tools": get_tools_schema(),
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    return headers, payload


def _handle_api_error(response):
    error_msg = f"API Error {response.status_code}"
    try:
        error_data = response.json()
        if "error" in error_data:
            error_msg += f": {error_data['error'].get('message', error_data['error'])}"
    except Exception:
        error_msg += f": {response.text[:200]}"
    printer.error(error_msg)


def _iter_sse_stream(response):
    """Yields parsed JSON objects from an SSE stream.

    We use a short requests read timeout, so iter_content may raise ReadTimeout.
    In that case, just continue waiting for more data.
    """
    buffer = ""
    for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
        if not chunk:
            continue
        buffer += chunk
        
        while True:
            line_end = buffer.find('\n')
            if line_end == -1:
                break

            line = buffer[:line_end].strip()
            buffer = buffer[line_end + 1:]

            if not line.startswith('data: '):
                continue

            data = line[6:]
            if data == '[DONE]':
                return

            try:
                yield json.loads(data)
            except json.JSONDecodeError as e:
                printer.debug(f"JSON decode error: {e} in: {data[:100]}")
                continue


def _process_tool_calls(tool_calls_list, tool_calls_by_index):
    for tc in tool_calls_list:
        idx = tc["index"]
        if idx not in tool_calls_by_index:
            tool_calls_by_index[idx] = {
                "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                "name": tc.get("function", {}).get("name", ""),
                "arguments": ""
            }

        if "function" in tc and "arguments" in tc["function"]:
            tool_calls_by_index[idx]["arguments"] += tc["function"]["arguments"]


def _print_usage(call_usage: dict, session):
    inp = call_usage.get("prompt_tokens", 0)
    out = call_usage.get("completion_tokens", 0)
    session.token_usage["input"] += inp
    session.token_usage["output"] += out
    session.turn_tokens_in += inp
    session.turn_tokens_out += out

    # Extract Anthropic prompt-cache metrics from prompt_tokens_details
    token_details = call_usage.get("prompt_tokens_details") or {}
    cached_tokens = token_details.get("cached_tokens", 0)
    cache_write_tokens = token_details.get("cache_write_tokens", 0)
    is_anthropic = _is_anthropic_model(config.MODEL)

    pricing = config.MODEL_PRICING.get(config.MODEL)
    if pricing:
        call_cost = (inp * pricing[0] + out * pricing[1]) / 1_000_000
        session.token_usage["cost"] += call_cost
        session.turn_cost += call_cost
        printer.usage(inp, out, call_cost,
                      session.turn_tokens_in, session.turn_tokens_out, session.turn_cost,
                      session.token_usage['input'], session.token_usage['output'], session.token_usage['cost'],
                      cached_tokens=cached_tokens, cache_write_tokens=cache_write_tokens,
                      show_cache=is_anthropic)
    else:
        printer.usage(inp, out, None,
                      session.turn_tokens_in, session.turn_tokens_out, None,
                      session.token_usage['input'], session.token_usage['output'], None,
                      cached_tokens=cached_tokens, cache_write_tokens=cache_write_tokens,
                      show_cache=is_anthropic)
