"""Tool registry and execution system."""

import json
import sys
from typing import Callable

# Global tool registry
_tools: dict[str, dict] = {}
_handlers: dict[str, Callable] = {}

class TurnCancelled(Exception):
    """Raised when user presses Escape to cancel the current turn."""
    pass

# Tools that require user confirmation
CONFIRM_TOOLS = {"write_file", "edit_file", "delete_file", "fetch_webpage", "web_search", "run_bash", "change_directory"}


def tool(name: str, description: str, params: dict, required: list[str] | None = None):
    """Decorator to register a tool with its schema."""
    def decorator(func: Callable) -> Callable:
        # Build JSON schema for parameters
        properties = {}
        for param_name, param_info in params.items():
            if isinstance(param_info, str):
                properties[param_name] = {"type": "string", "description": param_info}
            elif isinstance(param_info, dict):
                properties[param_name] = param_info
            else:
                properties[param_name] = {"type": "string"}

        schema = {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or []
            }
        }

        _tools[name] = schema
        _handlers[name] = func
        return func

    return decorator


def get_tools_schema() -> list[dict]:
    """Get all tools in OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"]
            }
        }
        for t in _tools.values()
    ]


def confirm_action(name: str, args: dict, session) -> bool:
    """Prompt user to confirm destructive actions. Returns True if confirmed."""
    if session.auto_confirm_turn:
        return True

    if name == "edit_file":
        detail = f"'{args.get('path')}' (replacing '{args.get('old_string', '')[:30]}...')"
    elif name == "fetch_webpage":
        detail = f"'{args.get('url')}'"
    elif name == "web_search":
        detail = f"'{args.get('query')}'"
    elif name == "run_bash":
        detail = f"'{args.get('command')}'"
    elif name == "change_directory":
        detail = f"'{args.get('path')}'"
    else:
        detail = f"'{args.get('path', 'unknown')}'"

    print(f"\nConfirm {name} {detail}? [y/n/!] ", end="", flush=True)
    try:
        response = input().strip().lower()
        if response == "!":
            session.auto_confirm_turn = True
            return True
        return response in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


def execute_tool(name: str, args: dict, session) -> str:
    """Execute a tool by name with given arguments."""
    if name in CONFIRM_TOOLS and not confirm_action(name, args, session):
        return "Tool call denied. Find another approach."

    handler = _handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"

    try:
        return handler(session=session, **args)
    except TypeError:
        # Handler doesn't need session
        return handler(**args)


# Import all tool modules to register them
from . import filesystem, search, web, shell
