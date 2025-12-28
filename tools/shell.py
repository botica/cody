"""Shell tools: run commands and change directory."""

import os
import subprocess

from . import tool


@tool(
    name="run_bash",
    description="Execute a bash/shell command and return the output. Can run Python scripts, git commands, npm, etc.",
    params={"command": "The command to execute (e.g., 'python script.py', 'git status', 'npm install')"},
    required=["command"]
)
def run_bash(command: str, session) -> str:
    # Handle pwd command to show current directory
    if command.strip() == "pwd":
        return session.cwd

    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=session.cwd,
            env=env
        )

        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line, end="", flush=True)
                output_lines.append(line)

        output = "".join(output_lines)
        return output if output else f"command executed successfully (exit code {process.returncode})"
    except subprocess.TimeoutExpired:
        process.kill()
        return "error: command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {e}"


@tool(
    name="change_directory",
    description="Change the current working directory. Affects where subsequent commands run.",
    params={"path": "The directory path to change to (e.g., '..', 'subfolder', '/absolute/path'). Empty string goes to home directory."},
    required=["path"]
)
def change_directory(path: str, session) -> str:
    # Handle empty path (go to home directory)
    if not path:
        try:
            session.cwd = os.path.expanduser("~")
            return f"Changed directory to {session.cwd}"
        except Exception as e:
            return f"Error: {e}"

    # Resolve the new path relative to current working directory
    try:
        new_path = os.path.abspath(os.path.join(session.cwd, path))
        if os.path.isdir(new_path):
            session.cwd = new_path
            return f"Changed directory to {session.cwd}"
        else:
            return f"Error: Directory not found: {new_path}"
    except Exception as e:
        return f"Error: {e}"
