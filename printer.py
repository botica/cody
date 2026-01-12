"""Print formatting and colors for cody"""

# ANSI 256-color codes
COLORS = {
    "reset": "\033[0m",
    "tool": "\033[38;5;75m",       # blue - tool names
    "arg": "\033[38;5;174m",       # soft dark pink - arguments, file items
    "info": "\033[38;5;42m",       # emerald - secondary info
    "bash": "\033[38;5;206m",      # hot pink - bash output
    "added": "\033[38;5;183m",     # light lavender - new/added
    "removed": "\033[48;5;233m\033[38;5;23m",  # dark grey bg, teal text - old/removed
    "reasoning": "\033[48;5;233m\033[38;5;23m", # super dark grey bg, teal text - reasoning
    "content": "\033[38;5;183m",   # light lavender - main output
    "banner": "\033[38;5;183m",    # light lavender - startup/prompt
    "stats": "\033[38;5;23m",      # teal - token stats
    "confirm": "\033[38;5;75m",    # blue - confirm prompts
    "user_input": "\033[48;5;23m\033[38;5;255m",  # dark teal bg, white text - user input
}

def c(color: str, text: str) -> str:
    """Wrap text in color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def tool_call(name: str, args_str: str = ""):
    """Print a tool call header."""
    if args_str:
        print(f"{c('tool', f'[{name}]')} {c('tool', args_str)}")
    else:
        print(f"{c('tool', f'[{name}]')}")


def tool_path(name: str, path: str):
    """Print a tool call with a path."""
    print(f"{c('tool', f'[{name}]')} {c('tool', path)}")


def edit_diff(path: str, old: str, new: str, max_lines: int = 4):
    """Print an edit_file diff preview."""
    print(f"{c('tool', '[edit_file]')} {c('tool', path)}")

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
            print(f"  {c('tool', f'  ... +{remaining} more lines')}")

    if old:
        show_lines(old, '-', 'removed')
    show_lines(new, '+', 'added')


def write_preview(path: str, content: str):
    """Print a write_file preview."""
    all_lines = content.splitlines()
    lines = all_lines[:10]
    preview = '\n'.join(f"  {c('tool', line[:100])}" for line in lines)
    if len(all_lines) > 10:
        preview += f"\n  {c('tool', f'... ({len(all_lines)} lines total)')}"
    print(f"{c('tool', '[write_file]')} {c('tool', path)}\n{preview}")


def reasoning(count: int):
    """Print reasoning block capture notice."""
    print(c('reasoning', f'[reasoning] captured {count} blocks'))


def limit_warning(cost: float):
    """Print turn cost limit warning."""
    print(c('tool', f"\n[limit] Turn exceeded ${cost:.2f}, cancelling"))


def item(text: str):
    """Print a list item (like directory entries)."""
    print(f"  {c('tool', text)}")


def search_result(title: str):
    """Print a search result title."""
    print(f"  {c('tool', f'- {title}')}")


def search_query(backend: str, query: str):
    """Print search query info."""
    print(f"{c('tool', f'[search:{backend}]')} {c('tool', repr(query))}")


def fetch_stats(method: str, raw: int, processed: int):
    """Print fetch/extraction stats."""
    reduction = 100 - processed / raw * 100 if raw > 0 else 0
    print(f"{c('tool', f'[{method}]')} {c('tool', f'{raw:,} -> {processed:,} chars ({reduction:.0f}% reduction)')}")


def fetch_browser_start():
    """Print browser launch message."""
    print(f"{c('tool', '[browser]')} {c('tool', 'launching...')}", end="", flush=True)


def fetch_browser_done():
    """Print browser done message."""
    print(c('tool', " done"))


# --- API / streaming ---

def error(msg: str):
    """Print an error message."""
    print(c('tool', f"[error] {msg}"))


def debug(msg: str):
    """Print a debug message."""
    print(c('tool', f"[debug] {msg}"))


def stream_reasoning(text: str):
    """Print streaming reasoning content."""
    # \033[K clears from cursor to end of line, preventing bg color bleed
    print(f"{COLORS['reasoning']}{text}{COLORS['reset']}\033[K", end="", flush=True)


def stream_content(text: str):
    """Print streaming content."""
    print(f"{COLORS['content']}{text}{COLORS['reset']}", end="", flush=True)


def newline():
    """Print a newline."""
    print()


def separator():
    """Print a separator between user input and response."""
    print(c('banner', "-----"))


def usage(call_in: int, call_out: int, call_cost: float | None,
          turn_in: int, turn_out: int, turn_cost: float | None,
          sess_in: int, sess_out: int, sess_cost: float | None):
    """Print token usage stats."""
    if call_cost is not None:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o ${call_cost:.4f}|turn: {turn_in:,}i/{turn_out:,}o ${turn_cost:.4f}|session: {sess_in:,}i/{sess_out:,}o ${sess_cost:.4f}"
    else:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o|turn: {turn_in:,}i/{turn_out:,}o|session: {sess_in:,}i/{sess_out:,}o"
    print(c('tool', msg))


def config_error():
    """Print API key configuration error."""
    print(c('tool', "Error: OPENROUTER_API_KEY not set"))
    print(c('tool', "Create a .env file with:"))
    print(c('tool', "  OPENROUTER_API_KEY=your_key_here"))


def banner(name: str, model: str):
    """Print startup banner."""
    print(f"{COLORS.get('banner', '')}{name} [{model}]{COLORS['reset']}")


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
