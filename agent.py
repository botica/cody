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
from tools import execute_tool, TurnCancelled


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
        assistant_msg = {
            "role": "assistant",
            "content": text or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"]
                    }
                }
                for tc in tool_calls
            ]
        }
        if reasoning_details:
            print(f"[reasoning] captured {len(reasoning_details)} blocks")
            assistant_msg["reasoning_details"] = reasoning_details
        session.conversation.append(assistant_msg)

        # Execute tools and add results
        try:
            for tc in tool_calls:
                args = json.loads(tc["arguments"])

                # Print tool args for visibility
                if args:
                    args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
                    print(f"({args_str})")
                else:
                    print()

                result = execute_tool(tc["name"], args, session)

                session.conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })
        except TurnCancelled:
            print("[turn cancelled]")
            break


def main():
    """Main entry point."""
    session = Session()
    print(f"Agent Cody Banks - license to code - {MODEL}")

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
