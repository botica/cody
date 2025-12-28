"""Cody - AI coding agent with tool use."""

import json
import sys

# Fix UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from config import Session, MODEL
from api import stream_completion
from tools import execute_tool


def run(prompt: str, session: Session) -> None:
    """Process a user prompt and handle the agent loop."""
    session.reset_turn()
    session.conversation.append({"role": "user", "content": prompt})

    while True:
        text, tool_calls, reasoning_details = stream_completion(session.conversation, session)

        if not tool_calls:
            # No tools called - conversation turn complete
            if text:
                msg = {"role": "assistant", "content": text}
                if reasoning_details:
                    msg["reasoning_details"] = reasoning_details
                session.conversation.append(msg)
            break

        # Build assistant message with tool calls
        def build_tool_call(tc, is_first=False):
            func_obj = {
                "name": tc["name"],
                "arguments": tc["arguments"]
            }
            # Gemini requires thought_signature for tool calls
            # Use dummy signature if not provided (per Google docs)
            if "gemini" in MODEL and is_first:
                func_obj["thought_signature"] = "placeholder"

            return {
                "id": tc["id"],
                "type": "function",
                "function": func_obj
            }

        assistant_msg = {
            "role": "assistant",
            "content": text or None,
            "tool_calls": [build_tool_call(tc, i == 0) for i, tc in enumerate(tool_calls)]
        }
        if reasoning_details:
            print(f"[reasoning] captured {len(reasoning_details)} blocks")
            assistant_msg["reasoning_details"] = reasoning_details
        session.conversation.append(assistant_msg)

        # Execute tools and add results
        for tc in tool_calls:
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except json.JSONDecodeError as e:
                session.conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": f"Error: Invalid JSON arguments: {e}"
                })
                continue

            # Print tool name with args
            if args:
                args_str = " ".join(f"{k}={repr(v)[:60]}" for k, v in args.items())
                print(f"[{tc['name']}] {args_str}")
            else:
                print(f"[{tc['name']}]")

            result = execute_tool(tc["name"], args, session)

            session.conversation.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result
            })


def main():
    """Main entry point."""
    session = Session()
    print(f"Cody [{MODEL}]")

    while True:
        try:
            prompt = input("> ")
            if prompt.strip():
                print()  # Newline after prompt
                run(prompt, session)
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)


if __name__ == "__main__":
    main()
