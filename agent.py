"""Cody (from the movie) terminal agent with tool"""

import json
import os
import sys
from dataclasses import dataclass, field

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SYSTEM_PROMPT = """
You are an AI agent named Cody. You assist the user with general tasks, coding tasks, and have tools available for usage.
Use your tools to complete the task. When searching the web, fetch at least one page for real content.
""".strip()


@dataclass
class Session:
    cwd: str = field(default_factory=os.getcwd)
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cost": 0.0})
    auto_confirm_turn: bool = False
    conversation: list = field(default_factory=list)

    def __post_init__(self):
        if not self.conversation:
            self.conversation = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reset_turn(self):
        self.auto_confirm_turn = False


from api import stream_completion, MODEL
from tools import execute_tool


def run(prompt: str, session: Session) -> None:
    session.reset_turn()
    session.conversation.append({"role": "user", "content": prompt})

    while True:
        text, tool_calls, reasoning_details = stream_completion(session.conversation, session)

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

    for delim in ('"""', '```'):
        if line.strip() == delim:
            # Just the delimiter
            lines = []
            while True:
                l = input()
                if l.strip() == delim:
                    break
                lines.append(l)
            return "\n".join(lines)
        elif line.rstrip().endswith(delim):
            # Context before delimiter: "fix this error """
            prefix = line.rstrip()[:-len(delim)].rstrip()
            lines = []
            while True:
                l = input()
                if l.strip() == delim:
                    break
                lines.append(l)
            return prefix + "\n" + "\n".join(lines)

    return line


def main():
    session = Session()
    print(f"Cody [{MODEL}]")
    print('Tip: Use """ or ``` for multi-line input')

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
