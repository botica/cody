"""OpenRouter API streaming and response handling."""

import json
import uuid
import requests

from tools import get_tools_schema
import printer
import config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Re-export config values for backwards compatibility
MODEL = config.MODEL
MODEL_PRICING = config.MODEL_PRICING
MAX_TURN_COST = config.MAX_TURN_COST
SHOW_REASONING = config.SHOW_REASONING


def check_config():
    """Check if API key is configured, prompt if missing."""
    if not config.API_KEY:
        if not config.prompt_api_key():
            return False
        # Reload the module-level constant
        config.API_KEY = config._cfg["api_key"]
    return True


def stream_completion(conversation: list, session) -> tuple[str, list[dict], dict | None]:
    headers = {
        "Authorization": f"Bearer {config.API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": conversation,
        "tools": get_tools_schema(),
        "stream": True,
        "stream_options": {"include_usage": True}
    }

    tool_calls_by_index = {}
    current_text = ""
    call_usage = None
    reasoning_details = None
    at_line_start = True
    had_reasoning = False

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=True, timeout=60)
    except requests.exceptions.RequestException as e:
        printer.error(f"Connection failed: {e}")
        return "", [], None

    with response:
        response.encoding = 'utf-8'  # Force UTF-8 (API returns UTF-8 but may not declare charset)
        if response.status_code != 200:
            error_msg = f"API Error {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f": {error_data['error'].get('message', error_data['error'])}"
            except Exception:
                error_msg += f": {response.text[:200]}"

            printer.error(error_msg)
            return "", [], None

        buffer = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
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
                    break

                try:
                    data_obj = json.loads(data)

                    if "usage" in data_obj:
                        call_usage = data_obj["usage"]

                    if not data_obj.get("choices"):
                        continue

                    delta = data_obj["choices"][0].get("delta", {})

                    if "reasoning_details" in data_obj["choices"][0].get("message", {}):
                        reasoning_details = data_obj["choices"][0]["message"]["reasoning_details"]
                    if "reasoning_details" in delta:
                        reasoning_details = delta["reasoning_details"]

                    reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                    if reasoning and SHOW_REASONING:
                        printer.stream_reasoning(reasoning)
                        at_line_start = reasoning.endswith('\n')
                        had_reasoning = True

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

                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            idx = tc["index"]
                            if idx not in tool_calls_by_index:
                                tool_calls_by_index[idx] = {
                                    "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                    "name": tc.get("function", {}).get("name", ""),
                                    "arguments": ""
                                }

                            if "function" in tc and "arguments" in tc["function"]:
                                tool_calls_by_index[idx]["arguments"] += tc["function"]["arguments"]

                except json.JSONDecodeError as e:
                    printer.debug(f"JSON decode error: {e} in: {data[:100]}")

    if not at_line_start:
        print(printer.COLORS['reset'], end='', flush=True)
        printer.newline()

    if call_usage:
        _print_usage(call_usage, session)

    tool_calls = list(tool_calls_by_index.values())
    return current_text, tool_calls, reasoning_details


def _print_usage(call_usage: dict, session):
    inp = call_usage.get("prompt_tokens", 0)
    out = call_usage.get("completion_tokens", 0)
    session.token_usage["input"] += inp
    session.token_usage["output"] += out
    session.turn_tokens_in += inp
    session.turn_tokens_out += out

    pricing = MODEL_PRICING.get(MODEL)
    if pricing:
        call_cost = (inp * pricing[0] + out * pricing[1]) / 1_000_000
        session.token_usage["cost"] += call_cost
        session.turn_cost += call_cost
        printer.usage(inp, out, call_cost,
                      session.turn_tokens_in, session.turn_tokens_out, session.turn_cost,
                      session.token_usage['input'], session.token_usage['output'], session.token_usage['cost'])
    else:
        printer.usage(inp, out, None,
                      session.turn_tokens_in, session.turn_tokens_out, None,
                      session.token_usage['input'], session.token_usage['output'], None)
