"""File system tools: read, write, edit, delete, list."""

import os
from pathlib import Path

from . import tool


@tool(
    name="read_file",
    description="Read the contents of a file",
    params={"path": "Path to the file to read"},
    required=["path"]
)
def read_file(path: str, session) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        with open(full_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool(
    name="list_directory",
    description="List files and directories in a path. If no path specified, use the current directory ('.').",
    params={"path": "Directory path to list"},
    required=[]
)
def list_directory(path: str = ".", session=None) -> str:
    try:
        cwd = session.cwd if session else os.getcwd()
        full_path = os.path.abspath(os.path.join(cwd, path))
        return "\n".join(os.listdir(full_path))
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


@tool(
    name="write_file",
    description="Create a new file or overwrite an existing file with content",
    params={
        "path": "Path to the file to create/overwrite",
        "content": "Content to write to the file"
    },
    required=["path", "content"]
)
def write_file(path: str, content: str, session) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool(
    name="edit_file",
    description="Edit a file by replacing a specific string with new content. The old_string must match exactly.",
    params={
        "path": "Path to the file to edit",
        "old_string": "The exact string to find and replace",
        "new_string": "The string to replace it with"
    },
    required=["path", "old_string", "new_string"]
)
def edit_file(path: str, old_string: str, new_string: str, session) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: old_string not found in {path}"

        count = content.count(old_string)
        if count > 1:
            return f"Error: old_string appears {count} times in {path}. Must be unique."

        new_content = content.replace(old_string, new_string, 1)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully edited {path}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


@tool(
    name="delete_file",
    description="Delete a file or empty directory",
    params={"path": "Path to the file or empty directory to delete"},
    required=["path"]
)
def delete_file(path: str, session) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        p = Path(full_path)
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
