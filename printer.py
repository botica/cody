"""Print formatting and colors for cody"""

# ANSI 256-color codes
COLORS = {
    "reset": "\033[0m",
    "blue": "\033[38;5;75m",
    "lavender": "\033[38;5;183m",
    "dim": "\033[48;5;233m\033[38;5;23m",  # dark grey bg, teal text
    "highlight": "\033[48;5;23m\033[38;5;255m",  # teal bg, white text
}

def c(color: str, text: str) -> str:
    """Wrap text in color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def tool_call(name: str, args: dict | str = None):
    """Print a tool call with appropriate formatting based on tool type."""
    if name == 'write_file' and isinstance(args, dict) and 'content' in args:
        write_preview(args.get('path', ''), args['content'])
    elif name == 'edit_file' and isinstance(args, dict):
        edit_diff(args.get('path', ''), args.get('old_string', ''), args.get('new_string', ''))
    elif isinstance(args, dict) and args:
        args_str = " ".join(f"{k}={str(v)[:60]}" for k, v in args.items())
        print(f"{c('blue', f'[{name}]')} {c('blue', args_str)}")
    elif isinstance(args, str) and args:
        print(f"{c('blue', f'[{name}]')} {c('blue', args)}")
    else:
        print(f"{c('blue', f'[{name}]')}")


def tool_path(name: str, path: str):
    """Print a tool call with a path."""
    print(f"{c('blue', f'[{name}]')} {c('blue', path)}")


def edit_diff(path: str, old: str, new: str, max_lines: int = 4):
    """Print an edit_file diff preview."""
    print(f"{c('blue', '[edit_file]')} {c('blue', path)}")

    def show_lines(text: str, prefix: str, color: str):
        lines = text.splitlines() if text else []
        preview_lines = [l for l in lines if l.strip()][:max_lines]
        total = len(lines)

        if not preview_lines:
            if total > 0:
                print(f"  {c(color, f'{prefix} ({total} empty lines)')}")
            return

        for line in preview_lines:
            print(f"  {c(color, f'{prefix} {line[:80]}')}")

        remaining = total - len(preview_lines)
        if remaining > 0:
            print(f"  {c('blue', f'  ... +{remaining} more lines')}")

    if old:
        show_lines(old, '-', 'dim')
    show_lines(new, '+', 'lavender')


def write_preview(path: str, content: str):
    """Print a write_file preview."""
    all_lines = content.splitlines()
    lines = all_lines[:10]
    preview = '\n'.join(f"  {c('blue', line[:100])}" for line in lines)
    if len(all_lines) > 10:
        preview += f"\n  {c('blue', f'... ({len(all_lines)} lines total)')}"
    print(f"{c('blue', '[write_file]')} {c('blue', path)}\n{preview}")


def reasoning(count: int):
    """Print reasoning block capture notice."""
    print(c('dim', f'[reasoning] captured {count} blocks'))


def limit_warning(cost: float):
    """Print turn cost limit warning."""
    print(c('blue', f"\n[limit] Turn exceeded ${cost:.2f}, cancelling"))


def item(text: str):
    """Print a list item (like directory entries)."""
    print(f"  {c('blue', text)}")


def search_result(title: str, url: str = ""):
    """Print a search result title and URL."""
    print(f"  {c('blue', f'- {title}')}")
    if url:
        print(f"  {c('blue', f'  {url}')}")


def search_query(backend: str, query: str):
    """Print search query info."""
    print(f"{c('blue', f'[search:{backend}]')} {c('blue', repr(query))}")


def fetch_stats(method: str, raw: int, processed: int):
    """Print fetch/extraction stats."""
    reduction = 100 - processed / raw * 100 if raw > 0 else 0
    print(f"{c('blue', f'[{method}]')} {c('blue', f'{raw:,} -> {processed:,} chars ({reduction:.0f}% reduction)')}")


def fetch_preview(text: str):
    """Print preview of first 10 lines (60 chars each)."""
    lines = [l for l in text.splitlines() if l.strip()][:10]
    if lines:
        print(f"  {c('blue', '[first 10 lines]')}")
        for line in lines:
            print(f"  {c('blue', line[:60])}")


def fetch_browser_start():
    """Print browser launch message."""
    print(f"{c('blue', '[browser]')} {c('blue', 'launching...')}", end="", flush=True)


def fetch_browser_done():
    """Print browser done message."""
    print(c('blue', " done"))


# --- API / streaming ---

def error(msg: str):
    """Print an error message."""
    print(c('blue', f"[error] {msg}"))


def debug(msg: str):
    """Print a debug message."""
    print(c('blue', f"[debug] {msg}"))


def stream_reasoning(text: str):
    """Print streaming reasoning content."""
    # \033[K clears from cursor to end of line, preventing bg color bleed
    print(f"{COLORS['dim']}{text}{COLORS['reset']}\033[K", end="", flush=True)


def stream_content(text: str):
    """Print streaming content."""
    print(f"{COLORS['lavender']}{text}{COLORS['reset']}", end="", flush=True)


def newline():
    """Print a newline."""
    print()


def separator():
    """Print a separator between user input and response."""
    print(c('lavender', "-----"))


def usage(call_in: int, call_out: int, call_cost: float | None,
          turn_in: int, turn_out: int, turn_cost: float | None,
          sess_in: int, sess_out: int, sess_cost: float | None):
    """Print token usage stats."""
    if call_cost is not None:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o ${call_cost:.4f}|turn: {turn_in:,}i/{turn_out:,}o ${turn_cost:.4f}|session: {sess_in:,}i/{sess_out:,}o ${sess_cost:.4f}"
    else:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o|turn: {turn_in:,}i/{turn_out:,}o|session: {sess_in:,}i/{sess_out:,}o"
    print(c('blue', msg))


def config_error():
    """Print API key configuration error."""
    print(c('blue', "error: OPENROUTER_API_KEY not set"))
    print(c('blue', "create a .env file with:"))
    print(c('blue', "  OPENROUTER_API_KEY=your_key_here"))


def banner(name: str, model: str):
    """Print startup banner."""
    print(f"{COLORS.get('lavender', '')}{name} [{model}]{COLORS['reset']}")


def confirm(name: str, detail: str):
    """Print confirmation prompt."""
    print(f"\n{c('blue', f'confirm {name} {detail}? [y/n/!]')} ", end="", flush=True)


def user_input(text: str, extra_lines: int = 0, prompt_len: int = 2):
    """Print user input with background highlight, replacing the echoed input."""
    import os
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80  # fallback

    lines = text.splitlines() or [""]

    # Calculate visual rows: each logical line may wrap based on terminal width
    visual_rows = extra_lines
    for i, line in enumerate(lines):
        # First line has the prompt, others don't
        line_len = len(line) + (prompt_len if i == 0 else 0)
        if line_len == 0:
            visual_rows += 1
        else:
            visual_rows += (line_len + term_width - 1) // term_width  # ceiling division

    # Clear all visual rows
    for _ in range(visual_rows):
        print("\033[1A\033[2K", end="", flush=True)
    # Print highlighted lines
    for line in lines:
        print(c('highlight', f' {line} '), flush=True)
