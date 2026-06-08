"""cody - terminal agent. this file is the loop, handling tool calls, user input, console reasoning/regular output. and slash commands."""

import argparse
import json
import os
import sys
import time
import signal
from dataclasses import dataclass, field

from datetime import datetime

from api import stream_completion, get_model, check_config, MAX_TURN_COST, SHOW_REASONING
from tools import execute_tool
import printer
import config

if sys.platform == 'win32':
    import io
    import os
    os.system('') # enables ANSI support in some windows environments
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_system_prompt(cwd: str) -> str:
    return config.SYSTEM_PROMPT_TEMPLATE.format(
        cwd=cwd,
        platform=sys.platform,
        date=datetime.now().strftime('%Y-%m-%d'),
        time=datetime.now().strftime('%H:%M')
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
    interrupted_at: float = 0.0
    exit_requested: bool = False

    def __post_init__(self):
        if not self.conversation:
            self.conversation = [{"role": "system", "content": get_system_prompt(self.cwd)}]

    def reset_turn(self):
        self.auto_confirm_turn = False
        self.turn_cost = 0.0
        self.turn_tokens_in = 0
        self.turn_tokens_out = 0


def run(prompt: str, session: Session) -> None:
    """Run a single user turn."""
    session.reset_turn()
    conversation_start = len(session.conversation)
    # Refresh system prompt so the model always has the current time
    if session.conversation and session.conversation[0]["role"] == "system":
        session.conversation[0]["content"] = get_system_prompt(session.cwd)
    session.conversation.append({"role": "user", "content": prompt})
    keep_upto = conversation_start + 1

    try:
        while True:
            if session.exit_requested:
                return

            text, tool_calls, reasoning_details = stream_completion(session.conversation, session)

            if session.turn_cost > MAX_TURN_COST:
                printer.limit_warning(MAX_TURN_COST)
                session.conversation = session.conversation[:keep_upto]
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

            denied = False
            for tc in tool_calls:
                if session.exit_requested:
                    break

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

                if isinstance(result, str) and result.startswith("TOOL_DENIED"):
                    denied = True
                    break
            if denied:
                break
    except KeyboardInterrupt:
        # Check if this was the second tap of a double-tap
        if (time.time() - session.interrupted_at) < 0.01: 
            # The signal handler already exited the process if it was < 0.5s.
            # If we are here, it means the signal handler raised KeyboardInterrupt.
            # However, on some systems, the race condition might lead us here.
            pass

        # Caught if the interrupt happens while Python code is running
        session.conversation = session.conversation[:keep_upto]
        printer.newline()
        print(printer.c('blue', '[turn cancelled]'))
        return


def handle_model_command(cmd: str):
    """Handle /model command for listing and switching models."""
    parts = cmd.split()

    # /model - list models
    if len(parts) == 1:
        printer.model_list(config.get_models())
        return

    # /model <n> - switch to model by number
    try:
        idx = int(parts[1]) - 1
        models = config.get_models()
        if 0 <= idx < len(models):
            name = models[idx][0]
            config.set_model(name)
            print(printer.c('blue', f'switched to {name}'))
        else:
            print(printer.c('blue', f'error: pick 1-{len(models)}'))
    except ValueError:
        print(printer.c('blue', 'usage: /model [n]'))


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


def _close_browser(session: Session) -> None:
    """Shut down the persistent Playwright browser if one was opened."""
    if getattr(session, '_browser', None):
        try:
            session._browser.close()
        except Exception:
            pass
    if getattr(session, '_playwright', None):
        try:
            session._playwright.stop()
        except Exception:
            pass


def _graceful_exit(session: Session | None = None, code: int = 0) -> None:
    """Exit.

    Keep this function non-blocking.

    On Windows, if a turn was cancelled with Ctrl-C, some libraries (requests,
    ddgs, playwright, concurrent.futures) may still be cleaning up threads.
    A subsequent Ctrl-C during Python's atexit/thread shutdown can produce noisy
    "Exception ignored" KeyboardInterrupt tracebacks.

    Without using the signal module, the most reliable way to avoid that is to
    hard-exit (skip atexit) if we've previously cancelled a turn.
    """
    if session:
        _close_browser(session)
    if session and getattr(session, "interrupted_at", 0.0):
        os._exit(code)
    raise SystemExit(code)


def setup_interrupt_handler(session: Session):
    def handler(signum, frame):
        now = time.time()
        # If the gap is less than 0.8s, it's a double-tap. Murder.
        if 0 < (now - session.interrupted_at) < 0.8:
            os._exit(0)
        
        session.interrupted_at = now
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handler)


def main():
    parser = argparse.ArgumentParser(description="cody terminal agent")
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
    setup_interrupt_handler(session)
    printer.banner("cody", get_model())

    last_hint_at = 0.0
    hint_printed = False
    while True:
        try:
            prompt, multiline = get_input()
            session.exit_requested = False
            hint_printed = False

            if prompt.strip() == "/clear":
                session.conversation = [{"role": "system", "content": get_system_prompt(session.cwd)}]
                session.token_usage = {"input": 0, "output": 0, "cost": 0.0}
                print(printer.c('blue', "[cleared]"))
                continue

            if prompt.strip().startswith("/model") or prompt.strip().startswith("/models"):
                printer.user_input(prompt)
                handle_model_command(prompt.strip())
                continue

            if prompt.strip():
                printer.user_input(prompt, extra_lines=2 if multiline else 0)
                run(prompt, session)
        except KeyboardInterrupt:
            # At the user prompt, we rely on the signal handler's double-tap (0.8s)
            # to handle the actual exit. One Ctrl-C here just shows the hint.
            now = time.time()
            if (now - session.interrupted_at) < 0.8:
                # Only print the hint if we haven't printed it yet this turn
                if not hint_printed:
                    sys.stdout.write("\r\033[K")
                    print(printer.c('blue', "(Ctrl-C again to exit)"))
                    hint_printed = True
                else:
                    # Just clear the current line (^C) and stay silent
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()
            session.exit_requested = True
        except EOFError:
            printer.newline()
            session.exit_requested = True
            _graceful_exit(session, 0)


if __name__ == "__main__":
    main()
