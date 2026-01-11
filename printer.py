"""Print formatting and colors for cody"""

# ANSI 256-color codes
COLORS = {
    "reset": "\033[0m",
    "tool": "\033[38;5;75m",       # blue - tool names
    "arg": "\033[38;5;229m",       # pale yellow - arguments, file items
    "info": "\033[38;5;240m",      # gray - secondary info
    "added": "\033[38;5;114m",     # green - new/added content
    "removed": "\033[38;5;203m",   # red - old/removed content
    "reasoning": "\033[38;5;210m", # pink - reasoning blocks
    "content": "\033[38;5;189m",   # lavender - main output
    "banner": "\033[38;5;216m",    # pale peach/orange - startup
    "stats": "\033[38;5;152m",     # pale steel blue - token stats
    "confirm": "\033[38;5;157m",   # light green - confirm prompts
    "user_input": "\033[48;5;236m\033[38;5;255m",  # dark gray bg, white text - user input
}

def c(color: str, text: str) -> str:
    """Wrap text in color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def tool_call(name: str, args_str: str = ""):
    """Print a tool call header."""
    if args_str:
        print(f"{c('tool', f'[{name}]')} {c('arg', args_str)}")
    else:
        print(f"{c('tool', f'[{name}]')}")


def tool_path(name: str, path: str):
    """Print a tool call with a path."""
    print(f"{c('tool', f'[{name}]')} {c('arg', path)}")


def edit_diff(path: str, old: str, new: str, insert_before: bool = False, insert_after: bool = False, max_lines: int = 4):
    """Print an edit_file diff preview."""
    print(f"{c('tool', '[edit_file]')} {c('arg', path)}")

    def show_lines(text: str, prefix: str, color: str):
        lines = text.splitlines() if text else []
        # Filter to non-empty lines for preview, but count all
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
            print(f"  {c('info', f'  ... +{remaining} more lines')}")

    if insert_after:
        # old is anchor, new is inserted after
        if old:
            show_lines(old, '@', 'info')  # anchor marker
        show_lines(new, '+', 'added')
    elif insert_before:
        # new is inserted before old (anchor)
        show_lines(new, '+', 'added')
        if old:
            show_lines(old, '@', 'info')  # anchor marker
    else:
        # replacement mode
        if old:
            show_lines(old, '-', 'removed')
        show_lines(new, '+', 'added')


def write_preview(path: str, content: str):
    """Print a write_file preview."""
    all_lines = content.splitlines()
    lines = all_lines[:10]
    preview = '\n'.join(f"  {c('arg', line[:100])}" for line in lines)
    if len(all_lines) > 10:
        preview += f"\n  {c('info', f'... ({len(all_lines)} lines total)')}"
    print(f"{c('tool', '[write_file]')} {c('arg', path)}\n{preview}")


def reasoning(count: int):
    """Print reasoning block capture notice."""
    print(c('reasoning', f'[reasoning] captured {count} blocks'))


def limit_warning(cost: float):
    """Print turn cost limit warning."""
    print(f"\n[limit] Turn exceeded ${cost:.2f}, cancelling")


def item(text: str):
    """Print a list item (like directory entries)."""
    print(f"  {c('arg', text)}")


def search_result(title: str):
    """Print a search result title."""
    print(f"  {c('arg', f'- {title}')}")


def search_query(backend: str, query: str):
    """Print search query info."""
    print(f"{c('tool', f'[search:{backend}]')} {c('arg', repr(query))}")


def fetch_stats(method: str, raw: int, processed: int):
    """Print fetch/extraction stats."""
    reduction = 100 - processed / raw * 100 if raw > 0 else 0
    print(f"{c('tool', f'[{method}]')} {c('arg', f'{raw:,} -> {processed:,} chars ({reduction:.0f}% reduction)')}")


def fetch_browser_start():
    """Print browser launch message."""
    print(f"{c('tool', '[browser]')} {c('arg', 'launching...')}", end="", flush=True)


def fetch_browser_done():
    """Print browser done message."""
    print(f" done{COLORS['reset']}")


# --- API / streaming ---

def error(msg: str):
    """Print an error message."""
    print(f"[error] {msg}")


def debug(msg: str):
    """Print a debug message."""
    print(f"[debug] {msg}")


def stream_reasoning(text: str):
    """Print streaming reasoning content."""
    print(c('reasoning', text), end="", flush=True)


def stream_content(text: str):
    """Print streaming content."""
    print(f"{COLORS['content']}{text}{COLORS['reset']}", end="", flush=True)


def newline():
    """Print a newline."""
    print()


def usage(call_in: int, call_out: int, call_cost: float | None,
          turn_in: int, turn_out: int, turn_cost: float | None,
          sess_in: int, sess_out: int, sess_cost: float | None):
    """Print token usage stats."""
    if call_cost is not None:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o ${call_cost:.4f}|turn: {turn_in:,}i/{turn_out:,}o ${turn_cost:.4f}|session: {sess_in:,}i/{sess_out:,}o ${sess_cost:.4f}"
    else:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o|turn: {turn_in:,}i/{turn_out:,}o|session: {sess_in:,}i/{sess_out:,}o"
    print(c('stats', msg))


def config_error():
    """Print API key configuration error."""
    print("Error: OPENROUTER_API_KEY not set")
    print("Create a .env file with:")
    print("  OPENROUTER_API_KEY=your_key_here")


def banner(name: str, model: str):
    """Print startup banner."""
    import time
    text = f"{name} [{model}]"
    print(COLORS.get('banner', ''), end='', flush=True)
    for char in text:
        print(char, end='', flush=True)
        time.sleep(0.015)
    print(COLORS['reset'])


def confirm(name: str, detail: str):
    """Print confirmation prompt."""
    print(f"\n{c('confirm', f'Confirm {name} {detail}? [y/n/!]')} ", end="", flush=True)


def user_input(text: str, extra_lines: int = 0):
    """Print user input with background highlight, replacing the echoed input."""
    lines = text.splitlines() or [""]
    # Clear all lines (content + any extra like multiline delimiters)
    for _ in range(len(lines) + extra_lines):
        print("\033[1A\033[2K", end="", flush=True)
    # Print highlighted lines
    for line in lines:
        print(c('user_input', f' {line} '), flush=True)
