"""Cody - terminal agent with tool"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

from api import stream_completion, MODEL, check_config, MAX_TURN_COST, SHOW_REASONING
from tools import execute_tool
import printer
import config

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_system_prompt(cwd: str) -> str:
    return config.SYSTEM_PROMPT_TEMPLATE.format(
        cwd=cwd,
        platform=sys.platform,
        date=datetime.now().strftime('%Y-%m-%d')
    )


@dataclass
class Session:
    cwd: str = field(default_factory=os.getcwd)
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cost": 0.0})
    turn_cost: float = 0.0
    turn_tokens_in: int = 0
    turn_tokens_out: int = 0
    auto_confirm_turn: bool = False
    yolo: bool = False
    conversation: list = field(default_factory=list)

    def __post_init__(self):
        if not self.conversation:
            self.conversation = [{"role": "system", "content": get_system_prompt(self.cwd)}]

    def reset_turn(self):
        self.auto_confirm_turn = False
        self.turn_cost = 0.0
        self.turn_tokens_in = 0
        self.turn_tokens_out = 0


def run(prompt: str, session: Session) -> None:
    session.reset_turn()
    conversation_start = len(session.conversation)
    session.conversation.append({"role": "user", "content": prompt})

    while True:
        text, tool_calls, reasoning_details = stream_completion(session.conversation, session)

        # Check cost limit
        if session.turn_cost > MAX_TURN_COST:
            printer.limit_warning(MAX_TURN_COST)
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
            assistant_msg["reasoning_details"] = reasoning_details
        session.conversation.append(assistant_msg)

        for tc in tool_calls:
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except json.JSONDecodeError as e:
                session.conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": f"error: invalid JSON arguments: {e}"
                })
                continue

            printer.tool_call(tc['name'], args)
            result = execute_tool(tc["name"], args, session)
            session.conversation.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result
            })


def get_input():
    line = input(printer.c('lavender', '> '))

    # Multiline mode: type --- and press enter, then paste content, then --- to finish
    if line.strip() == "---":
        lines = []
        while True:
            l = input()
            if l.strip() == "---":
                break
            lines.append(l)
        return "\n".join(lines), True

    return line, False


def main():
    parser = argparse.ArgumentParser(description="Cody terminal agent")
    parser.add_argument('--cwd', '-C', default=os.getcwd(), help='Working directory')
    parser.add_argument('--yolo', action='store_true', help='Skip all confirmations')
    args = parser.parse_args()

    cwd = os.path.abspath(args.cwd)
    if not os.path.isdir(cwd):
        printer.error(f"{cwd} is not a directory")
        sys.exit(1)

    if not check_config():
        sys.exit(1)

    session = Session(cwd=cwd, yolo=args.yolo)
    printer.banner("Cody", MODEL)

    while True:
        try:
            prompt, multiline = get_input()
            if prompt.strip() == "/clear":
                session.conversation = [{"role": "system", "content": get_system_prompt(session.cwd)}]
                session.token_usage = {"input": 0, "output": 0, "cost": 0.0}
                print("[cleared]")
                continue
            if prompt.strip():
                printer.user_input(prompt, extra_lines=2 if multiline else 0)
                run(prompt, session)
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)


if __name__ == "__main__":
    main()
