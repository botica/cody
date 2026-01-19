"""Tools and Schemas for cody"""

import inspect
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import trafilatura
from ddgs import DDGS
from playwright.sync_api import sync_playwright

import printer
import config

CONFIRM_TOOLS = config.CONFIRM_TOOLS

#helpers
def confirm_action(name: str, args: dict, session) -> bool | str:
    """Returns True to proceed, False to deny, or a string with user's custom response."""
    if session.yolo or session.auto_confirm_turn:
        return True

    if name == "edit_file":
        detail = f"'{args.get('path')}'"
    elif name in ("fetch_webpage", "web_search"):
        detail = f"'{args.get('url') or args.get('query')}'"
    elif name == "run_bash":
        detail = f"'{args.get('command')}'"
    else:
        detail = f"'{args.get('path', '')}'"

    printer.confirm(name, detail)
    try:
        response = input().strip()
        lower = response.lower()
        if lower == "!":
            session.auto_confirm_turn = True
            return True
        if lower in ("y", "yes"):
            return True
        if lower in ("n", "no"):
            return False
        if lower == "b":
            print(printer.c('blue', '> '), end='', flush=True)
            user_input = input().strip()
            if user_input:
                printer.user_input(user_input)
                return user_input
            return False
        return False
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


def execute_tool(name: str, args: dict, session) -> str:
    if name in CONFIRM_TOOLS:
        confirm_result = confirm_action(name, args, session)
        if confirm_result is False:
            return "tool call denied."
        if isinstance(confirm_result, str):
            return f"tool call denied. user response: {confirm_result}"

    handler = HANDLERS.get(name)
    if not handler:
        return f"unknown tool: {name}"

    sig = inspect.signature(handler)
    valid = set(sig.parameters.keys())
    filtered = {k: v for k, v in args.items() if k in valid}

    return handler(session=session, **filtered)


def _resolve_in_workspace(session, user_path: str) -> str:
    """Resolve a user-supplied path and ensure it stays within session.cwd.

    Accepts either a relative path (to session.cwd) or an absolute path that is
    still inside session.cwd.
    """
    if session is None or not getattr(session, "cwd", None):
        raise ValueError("session.cwd is required")

    workspace = Path(session.cwd).resolve()
    p = Path(user_path)
    if not p.is_absolute():
        p = workspace / p

    # resolve() (strict=False) prevents '..' traversal and follows symlinks.
    resolved = p.resolve(strict=False)

    try:
        resolved.relative_to(workspace)
    except Exception:
        raise PermissionError(f"path escapes workspace: {user_path}")

    return str(resolved)

#begin tool functions
def read_file(path: str, offset=None, limit=None, session=None) -> str:
    try:
        full_path = _resolve_in_workspace(session, path)
        if os.path.getsize(full_path) > config.FILE_SIZE_LIMIT:
            return f"error: file too large (>{config.FILE_SIZE_LIMIT // 1_000_000}MB): {path}"
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
    except PermissionError as e:
        return f"error: {e}"
    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as e:
        return f"error reading file: {e}"


def list_directory(path: str = ".", session=None) -> str:
    try:
        full_path = _resolve_in_workspace(session, path)
        items = os.listdir(full_path)
        for item in items:
            printer.item(item)
        return "\n".join(items)
    except PermissionError as e:
        return f"error: {e}"
    except Exception as e:
        return f"error: {e}"


def write_file(path: str, content: str, session=None) -> str:
    try:
        full_path = _resolve_in_workspace(session, path)
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"wrote {len(content)} bytes to {path}"
    except PermissionError as e:
        return f"error: {e}"
    except Exception as e:
        return f"error: {e}"


def edit_file(path: str, new_string: str = "", old_string: str = "", replace_all: bool = False, session=None) -> str:
    try:
        full_path = _resolve_in_workspace(session, path)
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        # If no old_string, append to end of file
        if not old_string:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content + new_string)
            return f"appended to {path}"

        if old_string not in content:
            lines = content.splitlines()
            old_start = old_string.split('\n')[0][:printer.SNIPPET_LEN]
            similar = [l.strip()[:printer.SNIPPET_LEN] for l in lines if old_start[:20].lower() in l.lower()][:3]
            hint = f" similar lines: {similar}" if similar else f" file has {len(lines)} lines."
            return f"error: old_string not found in {path}.{hint}"

        count = content.count(old_string)
        if count > 1 and not replace_all:
            return f"error: old_string appears {count} times in {path}. use replace_all=true to replace all."

        with open(full_path, "w", encoding="utf-8") as f:
            if replace_all:
                f.write(content.replace(old_string, new_string))
            else:
                f.write(content.replace(old_string, new_string, 1))

        suffix = f" ({count} replacements)" if replace_all and count > 1 else ""
        return f"edited {path}{suffix}"
    except PermissionError as e:
        return f"error: {e}"
    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as e:
        return f"error: {e}"


def delete_file(path: str, recursive: bool = False, session=None) -> str:
    try:
        full_path = _resolve_in_workspace(session, path)
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
                    return f"error: directory not empty. use recursive=true to delete: {path}"
        else:
            return f"error: not found: {path}"
        return f"deleted {path}"
    except PermissionError as e:
        return f"error: {e}"
    except Exception as e:
        return f"error: {e}"


def search(pattern: str, path: str = ".", file_pattern: str = None, session=None) -> str:
    try:
        full_path = _resolve_in_workspace(session, path)
        cmd = ["rg", pattern, full_path, "--color=never", "--max-count=50"]
        if file_pattern:
            cmd.extend(["-g", file_pattern])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 1:
            return "no matches found"
        return f"error: {result.stderr}"
    except PermissionError as e:
        return f"error: {e}"
    except FileNotFoundError:
        return "error: ripgrep (rg) not installed"
    except Exception as e:
        return f"error: {e}"


def fetch_webpage(url: str, use_browser: bool = False, session=None) -> str:

    def validate_url(u: str):
        """Validate and normalize a URL for fetching.
        """
        if not isinstance(u, str) or not u.strip():
            return None, "error: url must be a non-empty string"

        u = u.strip()
        parsed = urlparse(u)

        if parsed.scheme not in ("http", "https"):
            return None, f"error: only http(s) URLs are allowed (got scheme={parsed.scheme!r})"
        if not parsed.netloc or parsed.hostname is None:
            return None, "error: url must include a valid host"

        return u, None

    def get_headers():
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"}

    def process(text):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        print(printer.c('blue', f"{len(lines)} lines, {len(text)} chars"))
        return "\n".join(lines)

    def extract(html: str) -> str:
        """Extract main content using trafilatura"""
        text = trafilatura.extract(html, include_tables=True)
        if text:
            return text
        # Fallback to BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def with_requests():
        resp = requests.get(url, timeout=15, headers=get_headers())
        resp.raise_for_status()
        raw_len = len(resp.text)
        text = extract(resp.text)
        printer.fetch_stats("trafilatura", raw_len, len(text))
        printer.fetch_preview(text)
        return text

    def with_browser():
        printer.fetch_browser_start()
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("load")
            html = page.content()
            browser.close()
        printer.fetch_browser_done()
        raw_len = len(html)
        text = extract(html)
        printer.fetch_stats("trafilatura", raw_len, len(text))
        printer.fetch_preview(text)
        return text

    url, err = validate_url(url)
    if err:
        return err
    try:
        if use_browser:
            return process(with_browser())
        try:
            return process(with_requests())
        except Exception as e:
            print(printer.c('blue', f"{e}, trying browser..."))
            return process(with_browser())
    except Exception as e:
        print(printer.c('blue', f" error: {e}"))
        return f"error: {e}"


def web_search(query: str, backend: str = "auto", session=None) -> str:
    try:
        printer.search_query(backend, query)
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, backend=backend, max_results=5):
                title = r.get('title', '')
                printer.search_result(title, r.get('href', ''))
                results.append(f"- {title}\n  {r.get('href', '')}")
        return "\n\n".join(results) if results else "no results found"
    except Exception as e:
        return f"error: {e}"


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
            print(printer.c('blue', line.rstrip()))
            lines.append(line)
        try:
            exit_code = proc.wait(timeout=300)  # 5 min timeout
        except subprocess.TimeoutExpired:
            proc.kill()
            return "".join(lines) + "\n[error: command timed out after 5 minutes]"
        return "".join(lines) or f"done (exit {exit_code})"
    except Exception as e:
        return f"error: {e}"


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
            "path": {"type": "string", "description": "Path relative to workspace (session.cwd) or absolute path within workspace"},
            "offset": {"type": "integer", "description": "Starting line (1-indexed)"},
            "limit": {"type": "integer", "description": "Max lines to read"},
        },
        "required": ["path"]
    }},
    {"name": "list_directory", "description": "List all files and directories in a directory", "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Directory path relative to workspace (session.cwd) or absolute path within workspace"}},
        "required": ["path"]
    }},
    {"name": "write_file", "description": "Create a new file. Use edit_file to modify existing files.", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to workspace (session.cwd) or absolute path within workspace"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"]
    }},
    {"name": "edit_file", "description": "Modify existing files. Replaces old_string with new_string. Omit new_string to delete, omit old_string to append.", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to workspace or absolute path within workspace"},
            "new_string": {"type": "string", "description": "Replacement text (omit to delete old_string)"},
            "old_string": {"type": "string", "description": "Text to find and replace (omit to append new_string)"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences (default: false)"},
        },
        "required": ["path"]
    }},
    {"name": "delete_file", "description": "Delete a file or directory", "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to workspace (session.cwd) or absolute path within workspace"},
            "recursive": {"type": "boolean", "description": "Delete non-empty directories recursively (default: false)"},
        },
        "required": ["path"]
    }},
    {"name": "search", "description": "Search files with ripgrep", "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path": {"type": "string", "description": "Directory path relative to workspace (session.cwd) or absolute path within workspace"},
            "file_pattern": {"type": "string", "description": "Glob filter (e.g. *.py)"},
        },
        "required": ["pattern", "path"]
    }},
    {"name": "fetch_webpage", "description": "Fetch webpage text content. Extracts the main text and metadata, removing HTML tags, navigation, scripts, and styling (via trafilatura).", "parameters": {
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
    {"name": "run_bash", "description": "Run a shell command (use file tools for file operations)", "parameters": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Command to run"}},
        "required": ["command"]
    }},
]


def get_tools_schema() -> list[dict]:
    return [{"type": "function", "function": s} for s in SCHEMAS]
