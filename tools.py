"""Tools for cody"""

import inspect
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIRM_TOOLS = {"write_file", "edit_file", "delete_file", "fetch_webpage", "web_search", "run_bash"}


def confirm_action(name: str, args: dict, session) -> bool:
    if session.auto_confirm_turn:
        return True

    if name == "edit_file":
        detail = f"'{args.get('path')}' (replacing '{args.get('old_string', '')[:30]}...')"
    elif name in ("fetch_webpage", "web_search"):
        detail = f"'{args.get('url') or args.get('query')}'"
    elif name == "run_bash":
        detail = f"'{args.get('command')}'"
    else:
        detail = f"'{args.get('path', '')}'"

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
    if name in CONFIRM_TOOLS and not confirm_action(name, args, session):
        return "Tool call denied."

    handler = HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"

    sig = inspect.signature(handler)
    valid = set(sig.parameters.keys())
    filtered = {k: v for k, v in args.items() if k in valid}

    return handler(session=session, **filtered)


def read_file(path: str, offset=None, limit=None, session=None) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        if os.path.getsize(full_path) > 10_000_000:  # 10MB limit
            return f"Error: File too large (>10MB): {path}"
        with open(full_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        offset = int(offset) if offset else None
        limit = int(limit) if limit else None
        start = max(0, offset - 1) if offset else 0
        lines = lines[start:]
        if limit:
            lines = lines[:limit]

        result = [f"{start + i + 1:>6}| {line.rstrip()}" for i, line in enumerate(lines)]
        header = f"[{total} lines total]"
        if offset or limit:
            header += f" [showing lines {start + 1}-{start + len(lines)}]"
        return header + "\n" + "\n".join(result)
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(path: str = ".", session=None) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        result = "\n".join(os.listdir(full_path))
        print(result)
        return result
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str, session=None) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def edit_file(path: str, old_string: str, new_string: str, session=None) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: old_string not found in {path}"
        if content.count(old_string) > 1:
            return f"Error: old_string appears multiple times in {path}"

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content.replace(old_string, new_string, 1))
        return f"Edited {path}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error: {e}"


def delete_file(path: str, recursive: bool = False, session=None) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        p = Path(full_path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            if recursive:
                shutil.rmtree(full_path)
            else:
                try:
                    p.rmdir()
                except OSError:
                    return f"Error: Directory not empty. Use recursive=true to delete: {path}"
        else:
            return f"Error: Not found: {path}"
        return f"Deleted {path}"
    except Exception as e:
        return f"Error: {e}"


def search(pattern: str, path: str = ".", file_pattern: str = None, session=None) -> str:
    try:
        full_path = os.path.abspath(os.path.join(session.cwd, path))
        cmd = ["rg", pattern, full_path, "--color=never", "--max-count=50"]
        if file_pattern:
            cmd.extend(["-g", file_pattern])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 1:
            return "No matches found"
        return f"Error: {result.stderr}"
    except FileNotFoundError:
        return "Error: ripgrep (rg) not installed"
    except Exception as e:
        return f"Error: {e}"


def fetch_webpage(url: str, use_browser: bool = False, session=None) -> str:
    def get_headers():
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"}

    def process(text):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        print(f"{len(lines)} lines, {len(text)} chars")
        return "\n".join(lines)

    def with_requests():
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=15, headers=get_headers())
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def with_browser():
        from playwright.sync_api import sync_playwright
        print("[browser] launching...", end="", flush=True)
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            text = page.inner_text("body")
            browser.close()
        print(" done")
        return text

    try:
        if use_browser:
            return process(with_browser())
        try:
            return process(with_requests())
        except Exception as e:
            print(f"{e}, trying browser...")
            return process(with_browser())
    except Exception as e:
        return f"Error: {e}"


def web_search(query: str, backend: str = "auto", session=None) -> str:
    try:
        from ddgs import DDGS
        print(f"[search:{backend}] '{query}'")
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, backend=backend, max_results=5):
                title = r.get('title', '')
                print(f"  - {title}")
                results.append(f"- {title}\n  {r.get('href', '')}\n  {r.get('body', '')}")
        return "\n\n".join(results) if results else "No results found"
    except Exception as e:
        return f"Error: {e}"


def run_bash(command: str, session=None) -> str:
    if command.strip() == "pwd":
        return session.cwd
    try:
        proc = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=session.cwd, env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        lines = []
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
        try:
            exit_code = proc.wait(timeout=300)  # 5 min timeout
        except subprocess.TimeoutExpired:
            proc.kill()
            return "".join(lines) + "\n[Error: Command timed out after 5 minutes]"
        return "".join(lines) or f"Done (exit {exit_code})"
    except Exception as e:
        return f"Error: {e}"


HANDLERS = {
    "read_file": read_file,
    "list_directory": list_directory,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "search": search,
    "fetch_webpage": fetch_webpage,
    "web_search": web_search,
    "run_bash": run_bash,
}

SCHEMAS = [
    {"name": "read_file", "description": "Read a file's contents", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path"},
            "offset": {"type": "integer", "description": "Starting line (1-indexed)"},
            "limit": {"type": "integer", "description": "Max lines to read"},
        },
        "required": ["path"]
    }},
    {"name": "list_directory", "description": "List all files and directories in a directory", "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Directory path to list contents of"}},
        "required": ["path"]
    }},
    {"name": "write_file", "description": "Create or overwrite a file", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"]
    }},
    {"name": "edit_file", "description": "Replace a unique string in a file", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path"},
            "old_string": {"type": "string", "description": "String to find (must be unique)"},
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"]
    }},
    {"name": "delete_file", "description": "Delete a file or directory", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to delete"},
            "recursive": {"type": "boolean", "description": "Delete non-empty directories recursively (default: false)"},
        },
        "required": ["path"]
    }},
    {"name": "search", "description": "Search files with ripgrep", "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path": {"type": "string", "description": "Absolute directory path to search"},
            "file_pattern": {"type": "string", "description": "Glob filter (e.g. *.py)"},
        },
        "required": ["pattern", "path"]
    }},
    {"name": "fetch_webpage", "description": "Fetch webpage text content", "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "use_browser": {"type": "boolean", "description": "Use headless browser for JS sites"},
        },
        "required": ["url"]
    }},
    {"name": "web_search", "description": "Search the web. Returns titles, URLs, and brief snippets - not full page content", "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "backend": {"type": "string", "description": "Search engine: auto, bing, brave, duckduckgo, google, mojeek, yandex, yahoo, wikipedia"},
        },
        "required": ["query"]
    }},
    {"name": "run_bash", "description": "Run a shell command in the working directory", "parameters": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Command to run"}},
        "required": ["command"]
    }},
]


def get_tools_schema() -> list[dict]:
    return [{"type": "function", "function": s} for s in SCHEMAS]
