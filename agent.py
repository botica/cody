import json
import os
import subprocess
from pathlib import Path
from openai import OpenAI

SYSTEM_PROMPT = '''
You are an AI agent named Cody Banks. Your goal is to assist the user with coding tasks and other
requests. You have actionable tools available—use them freely and proactively without hesitation.
If you need to explore the filesystem, search directories (current, nested, or parent), list
directory contents, or read files to understand the codebase, do so. If you're curious about a
file, read it. Don't wait for explicit instructions to use tools.
'''.strip()

client = OpenAI()
RESULT_PREVIEW_LENGTH = 100

tools = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Read the contents of a file",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    },
    {
        "type": "function",
        "name": "list_directory",
        "description": "List files and directories in a path. If no path specified, use the current directory ('.').",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}}
        }
    },
    {
        "type": "function",
        "name": "search",
        "description": "Search for a pattern in files and return matching lines with file paths and line numbers. If no path specified, search the current directory ('.').",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The regex pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern for files to search (e.g., '*.py', '*.txt')"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Create a new file or overwrite an existing file with content",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to create/overwrite"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "type": "function",
        "name": "edit_file",
        "description": "Edit a file by replacing a specific string with new content. The old_string must match exactly.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace"
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace it with"
                }
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "type": "function",
        "name": "delete_file",
        "description": "Delete a file or empty directory",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or empty directory to delete"
                }
            },
            "required": ["path"]
        }
    }
]


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(path: str = ".") -> str:
    try:
        return "\n".join(os.listdir(path or "."))
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


def search(pattern: str, path: str = ".", file_pattern: str | None = None) -> str:
    try:
        cmd = ["rg.exe", pattern, path, "--color=never", "--max-count=50"]
        if file_pattern:
            cmd.extend(["-g", file_pattern])

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=10)

        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 1:
            return "No matches found"
        else:
            return f"Search error: {result.stderr}"
    except FileNotFoundError:
        return "Error: ripgrep (rg) is not installed."
    except subprocess.TimeoutExpired:
        return "Error: Search timed out"
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: old_string not found in {path}"

        count = content.count(old_string)
        if count > 1:
            return f"Error: old_string appears {count} times in {path}. Must be unique."

        new_content = content.replace(old_string, new_string, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully edited {path}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def delete_file(path: str) -> str:
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
            return f"Successfully deleted file: {path}"
        elif p.is_dir():
            p.rmdir()
            return f"Successfully deleted directory: {path}"
        else:
            return f"Error: Path not found: {path}"
    except OSError as e:
        return f"Error deleting: {e}"


def execute_tool(name: str, args: dict) -> str:
    tools_map = {
        "read_file": lambda: read_file(args["path"]),
        "list_directory": lambda: list_directory(args.get("path", ".")),
        "search": lambda: search(args["pattern"], args.get("path", "."), args.get("file_pattern")),
        "write_file": lambda: write_file(args["path"], args["content"]),
        "edit_file": lambda: edit_file(args["path"], args["old_string"], args["new_string"]),
        "delete_file": lambda: delete_file(args["path"]),
    }
    return tools_map.get(name, lambda: f"Unknown tool: {name}")()


def truncate(text: str, max_len: int = RESULT_PREVIEW_LENGTH) -> str:
    return f"{text[:max_len]}..." if len(text) > max_len else text


def run(prompt: str, conversation: list) -> None:
    conversation.append({"role": "user", "content": prompt})

    while True:
        stream = client.responses.create(
            model="gpt-5.2",
            input=conversation,
            tools=tools,
            reasoning={"effort": "medium"},
            text={"verbosity": "low"},
            stream=True
        )

        tool_calls = []
        current_text = ""
        pending_calls = {}

        for event in stream:
            match event.type:
                case "response.output_item.added" if event.item.type == "function_call":
                    item = event.item
                    print(f"[{item.name}] ", end="", flush=True)
                    pending_calls[item.id] = {"call_id": item.call_id, "name": item.name}

                case "response.function_call_arguments.done":
                    call_info = pending_calls.get(event.item_id, {})
                    name = call_info.get("name", "unknown")
                    call_id = call_info.get("call_id", event.item_id)
                    args = json.loads(event.arguments)
                    result = execute_tool(name, args)

                    print(args)
                    print(f"  {truncate(result)}\n")

                    tool_calls.append({
                        "call_id": call_id,
                        "name": name,
                        "arguments": event.arguments,
                        "result": result
                    })

                case "response.output_text.delta":
                    print(event.delta, end="", flush=True)
                    current_text += event.delta

                case "response.output_text.done" if current_text:
                    print()

        if not tool_calls:
            if current_text:
                conversation.append({"role": "assistant", "content": current_text})
            break

        for tc in tool_calls:
            conversation.append({
                "type": "function_call",
                "call_id": tc["call_id"],
                "name": tc["name"],
                "arguments": tc["arguments"]
            })
            conversation.append({
                "type": "function_call_output",
                "call_id": tc["call_id"],
                "output": tc["result"]
            })


if __name__ == "__main__":
    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        try:
            prompt = input("> ")
            if prompt.strip():
                run(prompt, conversation)
        except (KeyboardInterrupt, EOFError):
            break
