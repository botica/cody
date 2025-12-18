import json
import os
import re
from pathlib import Path
from openai import OpenAI

client = OpenAI()

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a path",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}}
            }
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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


def run(prompt):
    messages = [{"role": "user", "content": prompt}]

    while True:
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, tools=tools
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            print(msg.content)
            break

        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            print(f"[{name}] {args}")

            if name == "read_file":
                result = read_file(args["path"])
            elif name == "list_directory":
                result = list_directory(args.get("path", "."))
            elif name == "search":
                result = search(
                    args["pattern"],
                    args.get("path", "."),
                    args.get("file_pattern")
                )
            elif name == "write_file":
                result = write_file(args["path"], args["content"])
            elif name == "edit_file":
                result = edit_file(args["path"], args["old_string"], args["new_string"])
            elif name == "delete_file":
                result = delete_file(args["path"])

            print(f"  -> {result[:100]}{'...' if len(result) > 100 else ''}\n")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


if __name__ == "__main__":
    while True:
        try:
            prompt = input("> ")
            if prompt.strip():
                run(prompt)
        except (KeyboardInterrupt, EOFError):
            break
