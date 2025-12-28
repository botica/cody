"""Search tools using ripgrep."""

import os
import subprocess

from . import tool


@tool(
    name="search",
    description="Search for a pattern in files and return matching lines with file paths and line numbers. If no path specified, search the current directory ('.').",
    params={
        "pattern": "The regex pattern to search for",
        "path": "Directory to search in (default: current directory)",
        "file_pattern": "Glob pattern for files to search (e.g., '*.py', '*.txt')"
    },
    required=["pattern"]
)
def search(pattern: str, path: str = ".", file_pattern: str | None = None, session=None) -> str:
    try:
        cwd = session.cwd if session else os.getcwd()
        full_path = os.path.abspath(os.path.join(cwd, path))
        cmd = ["rg", pattern, full_path, "--color=never", "--max-count=50"]
        if file_pattern:
            cmd.extend(["-g", file_pattern])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=10)

        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 1:
            return "No matches found"
        else:
            return f"Search error: {result.stderr}"
    except FileNotFoundError:
        return "Error: ripgrep (rg) is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return "Error: Search timed out"
    except Exception as e:
        return f"Error: {e}"
