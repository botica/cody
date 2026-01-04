"""Cody (from the movie) terminal agent with tool"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

from api import stream_completion, MODEL, check_config, MAX_REQUEST_TOKENS
from tools import execute_tool

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_system_prompt(cwd: str) -> str:
    return f"""You are an AI agent named Cody. You assist the user with general tasks, coding tasks, and have tools available for usage.
Use your tools to complete the task. When searching the web, fetch at least one page for real content.
All file paths should be absolute paths. Use the working directory below as reference.

Environment:
- Working directory: {cwd}
- Platform: {sys.platform}
- Date: {datetime.now().strftime('%Y-%m-%d')}
"""


@dataclass
class Session:
    cwd: str = field(default_factory=os.getcwd)
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cost": 0.0})
    request_cost: float = 0.0
    request_tokens: int = 0
    auto_confirm_turn: bool = False
    conversation: list = field(default_factory=list)

    def __post_init__(self):
        if not self.conversation:
            self.conversation = [{"role": "system", "content": get_system_prompt(self.cwd)}]

    def reset_turn(self):
        self.auto_confirm_turn = False
        self.request_cost = 0.0
        self.request_tokens = 0


def run(prompt: str, session: Session) -> None:
    session.reset_turn()
    conversation_start = len(session.conversation)
    session.conversation.append({"role": "user", "content": prompt})

    while True:
        text, tool_calls, reasoning_details = stream_completion(session.conversation, session)

        # Check token limit
        if session.request_tokens > MAX_REQUEST_TOKENS:
            print(f"\n[limit] Request exceeded {MAX_REQUEST_TOKENS:,} tokens, cancelling")
            session.conversation = session.conversation[:conversation_start]
            break

        if not tool_calls:
            if text:
                msg = {"role": "assistant", "content": text}
                if reasoning_details:
                    msg["reasoning_details"] = reasoning_details
                session.conversation.append(msg)
            break

        def build_tool_call(tc):
            return {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]}
            }

        assistant_msg = {"role": "assistant", "tool_calls": [build_tool_call(tc) for tc in tool_calls]}
        if text:
            assistant_msg["content"] = text
        if reasoning_details:
            print(f"[reasoning] captured {len(reasoning_details)} blocks")
            assistant_msg["reasoning_details"] = reasoning_details
        session.conversation.append(assistant_msg)

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


def get_input():
    line = input("> ")

    for delim in ('"""', "'''"):
        prefix = ""
        if line.strip() == delim:
            pass  # Just the delimiter
        elif line.rstrip().endswith(delim):
            prefix = line.rstrip()[:-len(delim)].rstrip() + "\n"
        else:
            continue

        # Collect lines until closing delimiter
        lines = []
        while True:
            l = input()
            if l.strip() == delim:
                break
            if l.rstrip().endswith(delim):
                lines.append(l.rstrip()[:-len(delim)])
                break
            lines.append(l)
        return prefix + "\n".join(lines)

    return line


def main():
    parser = argparse.ArgumentParser(description="Cody terminal agent")
    parser.add_argument('--cwd', '-C', default=os.getcwd(), help='Working directory')
    args = parser.parse_args()

    cwd = os.path.abspath(args.cwd)
    if not os.path.isdir(cwd):
        print(f"Error: {cwd} is not a directory")
        sys.exit(1)

    if not check_config():
        sys.exit(1)

    session = Session(cwd=cwd)
    print(f"Cody [{MODEL}]")
    print(f"cwd: {cwd}")
    print("Tip: Use \"\"\" or ''' for multi-line input")

    while True:
        try:
            prompt = get_input()
            if prompt.strip():
                print()
                try:
                    run(prompt, session)
                except KeyboardInterrupt:
                    print("\n[interrupted]")
                    continue
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)


if __name__ == "__main__":
    main()
