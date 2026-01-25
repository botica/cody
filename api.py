"""OpenAI API streaming and response handling."""

import json
import uuid
from openai import OpenAI

from tools import get_tools_schema
import printer
import config

# Initialize OpenAI client
client = OpenAI(api_key=config.API_KEY)

# Re-export config values
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
        global client
        client = OpenAI(api_key=config.API_KEY)
    return True

def stream_completion(conversation: list, session) -> tuple[str, list[dict], dict | None]:
    try:
        stream = client.chat.completions.create(
            model=config.MODEL,
            messages=conversation,
            tools=get_tools_schema(),
            stream=True,
            stream_options={"include_usage": True}
        )
    except Exception as e:
        printer.error(f"OpenAI API request failed: {e}")
        return "", [], None

    # State for aggregation
    tool_calls_by_index = {}
    current_text = ""
    call_usage = None
    reasoning_details = None

    # State for display
    at_line_start = True
    had_reasoning = False

    for chunk in stream:
        # 1. Handle Usage
        if hasattr(chunk, 'usage') and chunk.usage:
            call_usage = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens
            }

        if not chunk.choices:
            continue

        choice = chunk.choices[0]
        delta = choice.delta

        # 2. Stream Reasoning Content (for o1/o3/gpt-5 models)
        reasoning = getattr(delta, 'reasoning_content', None)
        if reasoning and SHOW_REASONING:
            printer.stream_reasoning(reasoning)
            at_line_start = reasoning.endswith('\n')
            had_reasoning = True

        # 3. Stream Main Content
        content = delta.content
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
        if delta.tool_calls:
            _process_tool_calls(delta.tool_calls, tool_calls_by_index)

    # Final cleanup
    if not at_line_start:
        print(printer.COLORS['reset'], end='', flush=True)
        printer.newline()

    if call_usage:
        _print_usage(call_usage, session)

    return current_text, list(tool_calls_by_index.values()), reasoning_details

def _process_tool_calls(tool_calls_list, tool_calls_by_index):
    for tc in tool_calls_list:
        idx = tc.index
        if idx not in tool_calls_by_index:
            tool_calls_by_index[idx] = {
                "id": tc.id or f"call_{uuid.uuid4().hex[:8]}",
                "name": tc.function.name if tc.function and tc.function.name else "",
                "arguments": ""
            }

        if tc.function and tc.function.arguments:
            tool_calls_by_index[idx]["arguments"] += tc.function.arguments

def _print_usage(call_usage: dict, session):
    inp = call_usage.get("prompt_tokens", 0)
    out = call_usage.get("completion_tokens", 0)
    session.token_usage["input"] += inp
    session.token_usage["output"] += out
    session.turn_tokens_in += inp
    session.turn_tokens_out += out

    pricing = config.MODEL_PRICING.get(config.MODEL)
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
