import json
import os
import re
from pathlib import Path
from openai import OpenAI

client = OpenAI()

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
        "description": "List files and directories in a path",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}}
        }
    },
    {
        "type": "function",
        "name": "search",
        "description": "Search for a pattern in files. Returns matching lines with file paths and line numbers.",
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


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(path="."):
    if not path:
        path = "."
    try:
        return "\n".join(os.listdir(path))
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


def search(pattern, path=".", file_pattern=None):
    results = []
    root = Path(path)

    if file_pattern:
        files = root.rglob(file_pattern)
    else:
        files = root.rglob("*")

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    for file_path in files:
        if not file_path.is_file():
            continue
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        results.append(f"{file_path}:{line_num}: {line.rstrip()}")
                        if len(results) >= 50:
                            results.append("... (truncated, more results available)")
                            return "\n".join(results)
        except (PermissionError, OSError):
            continue

    if not results:
        return "No matches found"
    return "\n".join(results)


def write_file(path, content):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path, old_string, new_string):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: old_string not found in {path}"

        if content.count(old_string) > 1:
            return f"Error: old_string appears {content.count(old_string)} times in {path}. Must be unique."

        new_content = content.replace(old_string, new_string, 1)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully edited {path}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def delete_file(path):
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


def execute_tool(name, args):
    if name == "read_file":
        return read_file(args["path"])
    elif name == "list_directory":
        return list_directory(args.get("path", "."))
    elif name == "search":
        return search(
            args["pattern"],
            args.get("path", "."),
            args.get("file_pattern")
        )
    elif name == "write_file":
        return write_file(args["path"], args["content"])
    elif name == "edit_file":
        return edit_file(args["path"], args["old_string"], args["new_string"])
    elif name == "delete_file":
        return delete_file(args["path"])
    return f"Unknown tool: {name}"


def run(prompt, conversation):
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
        pending_calls = {}  # track call info by item_id

        for event in stream:
            if event.type == "response.output_item.added":
                item = event.item
                if item.type == "function_call":
                    print(f"[{item.name}] ...", end="", flush=True)
                    pending_calls[item.id] = {
                        "call_id": item.call_id,
                        "name": item.name
                    }
            elif event.type == "response.function_call_arguments.done":
                # Function call complete, execute it
                call_info = pending_calls.get(event.item_id, {})
                name = call_info.get("name", "unknown")
                call_id = call_info.get("call_id", event.item_id)

                args = json.loads(event.arguments)
                print(f"\r[{name}] {args}")

                result = execute_tool(name, args)
                print(f"  -> {result[:100]}{'...' if len(result) > 100 else ''}\n")

                tool_calls.append({
                    "call_id": call_id,
                    "name": name,
                    "arguments": event.arguments,
                    "result": result
                })
            elif event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
                current_text += event.delta
            elif event.type == "response.output_text.done":
                if current_text:
                    print()  # newline after text

        if not tool_calls:
            # Save assistant response to conversation
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
    conversation = []
    while True:
        try:
            prompt = input("> ")
            if prompt.strip():
                run(prompt, conversation)
        except (KeyboardInterrupt, EOFError):
            break
