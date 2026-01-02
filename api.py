"""OpenRouter API streaming and response handling."""

import json
import os
import requests

from tools import get_tools_schema


def _get_api_key():
    """Get API key from environment or config file."""
    # Check environment variable first
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    # Check config file
    config_path = os.path.expanduser("~/.cody/config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get("openrouter_api_key")
                if api_key:
                    return api_key
        except (json.JSONDecodeError, IOError):
            pass

    return None


OPENROUTER_API_KEY = _get_api_key()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

#MODEL = "google/gemini-3-flash-preview"
#MODEL = "x-ai/grok-code-fast-1"
MODEL = "minimax/minimax-m2.1"
#MODEL = "deepseek/deepseek-r1"
#MODEL = "openai/gpt-5.2"
#MODEL = "z-ai/glm-4.7"

MODEL_PRICING = {  # per million tokens (input, output)
    "google/gemini-3-flash-preview": (0.50, 3.00),
    "minimax/minimax-m2.1": (0.30, 1.20),
    "x-ai/grok-code-fast-1": (0.20, 1.50),
    "z-ai/glm-4.7": (0.40, 1.50),

    # OpenAI pricing (per 1M tokens): $1.75 input / $14.00 output
    "openai/gpt-5.2": (1.75, 14.00),
}


def stream_completion(conversation: list, session) -> tuple[str, list[dict], dict | None]:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
    turn_usage = None
    reasoning_details = None
    at_line_start = True
    had_reasoning = False

    with requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=True, timeout=60) as response:
        response.encoding = 'utf-8'  # Force UTF-8 (API returns UTF-8 but may not declare charset)
        if response.status_code != 200:
            error_msg = f"API Error {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f": {error_data['error'].get('message', error_data['error'])}"
            except Exception:
                error_msg += f": {response.text[:200]}"

            print(f"[error] {error_msg}")
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
                        turn_usage = data_obj["usage"]

                    if not data_obj.get("choices"):
                        continue

                    delta = data_obj["choices"][0].get("delta", {})

                    if "reasoning_details" in data_obj["choices"][0].get("message", {}):
                        reasoning_details = data_obj["choices"][0]["message"]["reasoning_details"]
                    if "reasoning_details" in delta:
                        reasoning_details = delta["reasoning_details"]

                    reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                    if reasoning:
                        print(f"\033[38;5;210m{reasoning}\033[0m", end="", flush=True)
                        at_line_start = reasoning.endswith('\n')
                        had_reasoning = True

                    content = delta.get("content")
                    if content:
                        if had_reasoning:
                            if not at_line_start:
                                print()
                            print()
                            had_reasoning = False
                        print(content, end="", flush=True)
                        current_text += content
                        at_line_start = content.endswith('\n')

                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            idx = tc["index"]
                            if idx not in tool_calls_by_index:
                                tool_calls_by_index[idx] = {
                                    "id": tc.get("id", ""),
                                    "name": tc.get("function", {}).get("name", ""),
                                    "arguments": ""
                                }

                            if "function" in tc and "arguments" in tc["function"]:
                                tool_calls_by_index[idx]["arguments"] += tc["function"]["arguments"]

                except json.JSONDecodeError as e:
                    print(f"[debug] JSON decode error: {e} in: {data[:100]}")

    if not at_line_start:
        print()

    if turn_usage:
        _print_usage(turn_usage, session)

    tool_calls = list(tool_calls_by_index.values())
    return current_text, tool_calls, reasoning_details


def _print_usage(turn_usage: dict, session):
    inp = turn_usage.get("prompt_tokens", 0)
    out = turn_usage.get("completion_tokens", 0)
    session.token_usage["input"] += inp
    session.token_usage["output"] += out

    pricing = MODEL_PRICING.get(MODEL)
    if pricing:
        turn_cost = (inp * pricing[0] + out * pricing[1]) / 1_000_000
        session.token_usage["cost"] += turn_cost
        print(f"[tokens] +{inp:,} in, +{out:,} out (${turn_cost:.4f}) | session: ${session.token_usage['cost']:.4f}")
    else:
        print(f"[tokens] +{inp:,} in, +{out:,} out | session: {session.token_usage['input']:,} in, {session.token_usage['output']:,} out")
