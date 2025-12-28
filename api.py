"""OpenRouter API streaming and response handling."""

import json
import requests

from config import OPENROUTER_API_KEY, OPENROUTER_URL, MODEL, MODEL_PRICING
from tools import get_tools_schema


def stream_completion(conversation: list, session) -> tuple[str, list[dict], dict | None]:
    """
    Stream a completion from OpenRouter.

    Returns:
        tuple: (text_content, tool_calls, reasoning_details)
    """
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
    at_line_start = True  # Track cursor position to avoid extra newlines
    had_reasoning = False  # Track if we need newline before content

    with requests.post(OPENROUTER_URL, headers=headers, json=payload, stream=True) as response:
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
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

                    # Capture usage if present
                    if "usage" in data_obj:
                        turn_usage = data_obj["usage"]

                    # Skip if no choices (usage-only chunk)
                    if not data_obj.get("choices"):
                        continue

                    delta = data_obj["choices"][0].get("delta", {})

                    # Handle reasoning details (for models like minimax that use reasoning)
                    if "reasoning_details" in data_obj["choices"][0].get("message", {}):
                        reasoning_details = data_obj["choices"][0]["message"]["reasoning_details"]
                    if "reasoning_details" in delta:
                        reasoning_details = delta["reasoning_details"]

                    # Handle streaming reasoning content (deepseek-r1, etc.)
                    reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                    if reasoning:
                        print(f"\033[38;5;210m{reasoning}\033[0m", end="", flush=True)
                        at_line_start = reasoning.endswith('\n')
                        had_reasoning = True

                    # Handle text content
                    content = delta.get("content")
                    if content:
                        if had_reasoning:
                            if not at_line_start:
                                print()
                            print()  # Blank line between reasoning and output
                            had_reasoning = False
                        print(content, end="", flush=True)
                        current_text += content
                        at_line_start = content.endswith('\n')

                    # Handle tool calls (accumulate silently, print in agent.py)
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

                except json.JSONDecodeError:
                    pass

    # Newline after content if needed
    if current_text and not at_line_start:
        print()
    if current_text:
        print()  # Blank line before token line

    # Print token usage
    if turn_usage:
        _print_usage(turn_usage, session)

    tool_calls = list(tool_calls_by_index.values())
    return current_text, tool_calls, reasoning_details


def _print_usage(turn_usage: dict, session):
    """Print and accumulate token usage."""
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
