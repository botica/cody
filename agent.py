import json
import os
import subprocess
import sys
from pathlib import Path
from openai import OpenAI

SYSTEM_PROMPT = '''
You are an AI agent named Cody. Your goal is to assist the user with coding tasks and other
requests. You have actionable tools available—use them freely and proactively without hesitation.
If you need to explore the filesystem, search directories, list
directory contents, or read files to understand the codebase, do so. If you're curious about a
file, read it.

IMPORTANT: You have a strict limit of 4 tool calls per response. After gathering initial
information, STOP and summarize what you found. Do NOT exhaustively check multiple sources.
One good source is enough. The user can ask follow-up if they need more info.
'''.strip()

client = OpenAI()

# Track current working directory across commands
current_working_dir = os.getcwd()

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
    },
    {
        "type": "function",
        "name": "fetch_webpage",
        "description": "Fetch a webpage and extract its text content. Use use_browser=true for JavaScript-heavy sites.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch"
                },
                "use_browser": {
                    "type": "boolean",
                    "description": "Use headless browser (Playwright) for JS-rendered content. Default: false"
                }
            },
            "required": ["url"]
        }
    },
    {
        "type": "function",
        "name": "web_search",
        "description": "Search the web using DuckDuckGo. Returns titles, URLs, and snippets of search results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "function",
        "name": "run_bash",
        "description": "Execute a bash/shell command and return the output. Can run Python scripts, git commands, npm, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute (e.g., 'python script.py', 'git status', 'npm install')"
                }
            },
            "required": ["command"]
        }
    },
    {
        "type": "function",
        "name": "change_directory",
        "description": "Change the current working directory. Affects where subsequent commands run.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to change to (e.g., '..', 'subfolder', '/absolute/path'). Empty string goes to home directory."
                }
            },
            "required": ["path"]
        }
    }
]


def read_file(path: str) -> str:
    try:
        # Resolve path relative to current working directory
        full_path = os.path.abspath(os.path.join(current_working_dir, path))
        with open(full_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as e:
        return f"error reading file: {e}"


def list_directory(path: str = ".") -> str:
    try:
        # Resolve path relative to current working directory
        full_path = os.path.abspath(os.path.join(current_working_dir, path))
        return "\n".join(os.listdir(full_path))
    except FileNotFoundError:
        return f"error: directory not found: {path}"
    except Exception as e:
        return f"error listing directory: {e}"


def search(pattern: str, path: str = ".", file_pattern=None) -> str:
    try:
        # Resolve path relative to current working directory
        full_path = os.path.abspath(os.path.join(current_working_dir, path))
        cmd = ["rg", pattern, full_path, "--color=never", "--max-count=50"]
        if file_pattern:
            cmd.extend(["-g", file_pattern])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", timeout=10)

        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode == 1:
            return "no matches found"
        else:
            return f"search error: {result.stderr}"
    except FileNotFoundError:
        return "error: ripgrep (rg) is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return "error: search timed out"
    except Exception as e:
        return f"error: {e}"


def write_file(path: str, content: str) -> str:
    try:
        # Resolve path relative to current working directory
        full_path = os.path.abspath(os.path.join(current_working_dir, path))
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"error writing file: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    try:
        # Resolve path relative to current working directory
        full_path = os.path.abspath(os.path.join(current_working_dir, path))
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        if old_string not in content:
            return f"error: old_string not found in {path}"

        count = content.count(old_string)
        if count > 1:
            return f"error: old_string appears {count} times in {path}, must be unique"

        new_content = content.replace(old_string, new_string, 1)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"successfully edited {path}"
    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as e:
        return f"error editing file: {e}"


def delete_file(path: str) -> str:
    try:
        # Resolve path relative to current working directory
        full_path = os.path.abspath(os.path.join(current_working_dir, path))
        p = Path(full_path)
        if p.is_file():
            p.unlink()
            return f"successfully deleted file: {path}"
        elif p.is_dir():
            p.rmdir()
            return f"successfully deleted directory: {path}"
        else:
            return f"error: path not found: {path}"
    except OSError as e:
        return f"error deleting: {e}"


def fetch_webpage(url: str, use_browser: bool = False) -> str:
    from fake_useragent import UserAgent
    ua = UserAgent()

    def get_headers():
        return {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    def fetch_with_browser(url: str) -> str:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
        print("[browser] launching stealth playwright...", end="", flush=True)
        with Stealth().use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=ua.random,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/Chicago",
            )
            page = context.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)  # let JS render
            text = page.inner_text("body")
            browser.close()
        print(" done")
        return text

    def fetch_with_requests(url: str) -> str:
        import requests
        from bs4 import BeautifulSoup
        session = requests.Session()
        headers = get_headers()
        response = session.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        print(f"[requests] status={response.status_code}, parsing...", end="", flush=True)

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        print(" done")
        return text

    def process_text(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)
        print(f"{len(lines)} lines, {len(text)} chars")
        return text

    try:
        if use_browser:
            text = fetch_with_browser(url)
            return process_text(text)

        # Try requests first, fall back to browser on failure
        try:
            text = fetch_with_requests(url)
            return process_text(text)
        except Exception as req_err:
            print(f"{req_err}")
            print("retrying with stealth playwright")
            try:
                text = fetch_with_browser(url)
                return process_text(text)
            except Exception as browser_err:
                print(f"playwright failed: {browser_err}")
                return f"error fetching {url}: requests failed ({req_err}), browser also failed ({browser_err})"
    except Exception as e:
        print(f"{e}")
        return f"error fetching {url}: {e}"


def web_search(query: str) -> str:
    try:
        from ddgs import DDGS

        print(f"[search] querying '{query}'")
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                title = r.get("title", "")
                href = r.get("href", "")
                body = r.get("body", "")
                print(f"{title}")
                results.append(f"- {title}\n  {href}\n  {body}")

        if not results:
            print("(no results)")
            return "no search results found"

        return "\n\n".join(results)
    except Exception as e:
        print(f"error: {e}")
        return f"error searching: {e}"


def change_directory(path: str) -> str:
    global current_working_dir

    # Handle empty path (go to home directory)
    if not path:
        try:
            current_working_dir = os.path.expanduser("~")
            return f"changed directory to {current_working_dir}"
        except Exception as e:
            return f"error: {e}"

    # Resolve the new path relative to current working directory
    try:
        new_path = os.path.abspath(os.path.join(current_working_dir, path))
        if os.path.isdir(new_path):
            current_working_dir = new_path
            return f"changed directory to {current_working_dir}"
        else:
            return f"error: directory not found: {new_path}"
    except Exception as e:
        return f"error: {e}"


def run_bash(command: str) -> str:
    # Handle pwd command to show current directory
    if command.strip() == "pwd":
        return current_working_dir

    # Run commands in the current working directory with real-time output
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
            cwd=current_working_dir,
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
        return f"error executing command: {e}"


CONFIRM_TOOLS = {"write_file", "edit_file", "delete_file", "fetch_webpage", "web_search", "run_bash", "change_directory"}


def confirm_action(name: str, args: dict) -> bool:
    """Prompt user to confirm destructive actions. Returns True if confirmed."""
    if name == "edit_file":
        detail = f"'{args.get('path')}' (replacing '{args.get('old_string', '')}')"
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

    print(f"\nConfirm {name} {detail}? [YES/no] ", end="", flush=True)
    try:
        response = input().strip().lower()
        return response in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)


def execute_tool(name: str, args: dict) -> str:
    if name in CONFIRM_TOOLS and not confirm_action(name, args):
        return "tool call denied. find another approach."

    if name == "read_file":
        return read_file(args["path"])
    elif name == "list_directory":
        return list_directory(args.get("path", "."))
    elif name == "search":
        return search(args["pattern"], args.get("path", "."), args.get("file_pattern"))
    elif name == "write_file":
        return write_file(args["path"], args["content"])
    elif name == "edit_file":
        return edit_file(args["path"], args["old_string"], args["new_string"])
    elif name == "delete_file":
        return delete_file(args["path"])
    elif name == "fetch_webpage":
        return fetch_webpage(args["url"], args.get("use_browser", False))
    elif name == "web_search":
        return web_search(args["query"])
    elif name == "run_bash":
        return run_bash(args["command"])
    elif name == "change_directory":
        return change_directory(args["path"])
    else:
        return f"unknown tool: {name}"


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
                    if current_text:
                        print()  # newline to separate text from tool call
                    item = event.item
                    print(f"[{item.name}] ", end="", flush=True)
                    pending_calls[item.id] = {"call_id": item.call_id, "name": item.name}

                case "response.function_call_arguments.done":
                    call_info = pending_calls.get(event.item_id, {})
                    name = call_info.get("name", "unknown")
                    call_id = call_info.get("call_id", event.item_id)
                    args = json.loads(event.arguments)

                    # Print tool args for visibility
                    if args:
                        args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
                        print(f"({args_str})")
                    else:
                        print()

                    result = execute_tool(name, args)

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
                    print('')

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
            print()
            sys.exit(0)
