"""Print formatting and colors for cody"""

SNIPPET_LEN = 80

# ANSI 256-color codes
COLORS = {
    "reset": "\033[0m",
    "blue": "\033[38;5;75m",
    "lavender": "\033[38;5;183m",
    "dim": "\033[48;5;233m\033[38;5;23m",  # dark grey bg, teal text
    "highlight": "\033[48;5;23m\033[38;5;255m",  # teal bg, white text
    "del": "\033[48;5;234m\033[38;5;23m",  # teal text, grey bg
    "add": "\033[48;5;235m\033[38;5;183m",  # lighter grey bg, lavender text
}

def c(color: str, text: str) -> str:
    """Wrap text in color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def _edit_file_preview(args: dict):
    """Print edit_file preview with context and diff."""
    path = args.get('path', '')
    old_string = args.get('old_string', '')
    new_string = args.get('new_string', '')
    start_line = None
    ctx_before = ctx_after = None
    old_lines = new_lines = None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Find the correct occurrence (1-indexed), default to first
        occurrence = args.get('occurrence', 1) or 1
        idx = -1
        search_start = 0
        for _ in range(occurrence):
            idx = content.find(old_string, search_start)
            if idx == -1:
                break
            search_start = idx + 1
        if idx >= 0:
            start_line = content[:idx].count('\n') + 1
            end_line = start_line + old_string.count('\n')
            lines = content.splitlines()
            old_lines = '\n'.join(lines[start_line - 1:end_line])
            new_lines = old_lines.replace(old_string, new_string, 1)
            if start_line > 1:
                ctx_before = lines[start_line - 2]
            if end_line < len(lines):
                ctx_after = lines[end_line]
    except Exception as e:
        print(c('blue', f'[edit_file] failed to read {path}: {e}'))
        old_lines, new_lines = old_string, new_string
    edit_diff(path, old_lines or old_string, new_lines or new_string,
              start_line=start_line, ctx_before=ctx_before, ctx_after=ctx_after,
              old_fragment=old_string, new_fragment=new_string)


def tool_call(name: str, args: dict | str = None):
    """Print a tool call with appropriate formatting based on tool type."""
    if name == 'write_file' and isinstance(args, dict) and 'content' in args:
        write_preview(args.get('path', ''), args['content'])
    elif name == 'edit_file' and isinstance(args, dict):
        _edit_file_preview(args)
    elif isinstance(args, dict) and args:
        args_str = " ".join(f"{k}={str(v)[:SNIPPET_LEN]}" for k, v in args.items())
        print(f"{c('blue', f'[{name}]')} {c('blue', args_str)}")
    elif isinstance(args, str) and args:
        print(f"{c('blue', f'[{name}]')} {c('blue', args)}")
    else:
        print(f"{c('blue', f'[{name}]')}")


def tool_path(name: str, path: str):
    """Print a tool call with a path."""
    print(f"{c('blue', f'[{name}]')} {c('blue', path)}")


def edit_diff(path: str, old: str, new: str, max_lines: int = 5, start_line: int = None,
              ctx_before: str = None, ctx_after: str = None,
              old_fragment: str = None, new_fragment: str = None):
    """Print an edit_file diff preview with context and highlighted changes."""
    print(f"{c('blue', '[edit_file]')} {c('blue', path)}")

    def show_ctx(line_num: int, text: str):
        if text is not None:
            print(f"  {c('blue', f'{line_num:4}   {text[:SNIPPET_LEN]}')}")

    def highlight_line(line: str, fragment: str, base_color: str, hl_color: str):
        """Highlight fragment within line using hl_color, rest in base_color."""
        if not fragment or fragment not in line:
            return c(base_color, line[:SNIPPET_LEN])

        idx = line.find(fragment)
        frag_len = len(fragment)

        # Center the window on the middle of the fragment
        frag_center = idx + frag_len // 2
        start = max(0, frag_center - SNIPPET_LEN // 2)
        end = start + SNIPPET_LEN

        # Adjust if we hit the end of the line
        if end > len(line):
            end = len(line)
            start = max(0, end - SNIPPET_LEN)

        trunc = line[start:end]

        # Recalculate index in truncated view
        new_idx = idx - start
        frag_end = min(new_idx + frag_len, len(trunc))
        before = trunc[:new_idx] if new_idx > 0 else ''
        frag = trunc[new_idx:frag_end]
        after = trunc[frag_end:]

        # Build the result with ellipsis for context
        prefix = c(base_color, '...') if start > 0 else ''
        suffix = c(base_color, '...') if end < len(line) else ''
        return prefix + c(base_color, before) + c(hl_color, frag) + c(base_color, after) + suffix

    def show_lines(text: str, prefix: str, base_color: str, hl_color: str, fragment: str, line_num: int = None):
        lines = text.splitlines() if text else []
        total = len(lines)

        if not lines or not any(l.strip() for l in lines):
            if total > 0:
                print(f"  {c(base_color, f'     {prefix} ({total} empty lines)')}")
            return

        # Track which lines contain the fragment (for multiline fragments)
        frag_lines = fragment.splitlines() if fragment else []
        frag_idx = 0

        shown = 0
        for i, line in enumerate(lines):
            if shown >= max_lines:
                break
            ln = f"{line_num + i:4} " if line_num else "     "
            # Find if this line has part of the fragment
            frag_part = frag_lines[frag_idx] if frag_idx < len(frag_lines) else None
            highlighted = highlight_line(line, frag_part, base_color, hl_color) if line else ""
            print(f"  {c(base_color, f'{ln}{prefix} ')}{highlighted}")
            if frag_part and frag_part in line:
                frag_idx += 1
            shown += 1

        remaining = total - shown
        if remaining > 0:
            print(f"  {c('blue', f'     ... +{remaining} more lines')}")

    # Context before
    if ctx_before is not None and start_line:
        show_ctx(start_line - 1, ctx_before)

    if old:
        show_lines(old, '-', 'dim', 'del', old_fragment, start_line)
    show_lines(new, '+', 'lavender', 'add', new_fragment, start_line)

    # Context after
    if ctx_after is not None and start_line:
        end_line = start_line + max(old.count('\n'), new.count('\n'))
        show_ctx(end_line + 1, ctx_after)


def write_preview(path: str, content: str):
    """Print a write_file preview."""
    all_lines = content.splitlines()
    lines = all_lines[:10]
    preview = '\n'.join(f"  {c('blue', line[:SNIPPET_LEN])}" for line in lines)
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
    """Print preview of first 3 lines."""
    lines = [l for l in text.splitlines() if l.strip()][:3]
    if lines:
        print(f"  {c('blue', '[first 3 lines]')}")
        for line in lines:
            print(f"  {c('blue', line[:SNIPPET_LEN])}")


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
          sess_in: int, sess_out: int, sess_cost: float | None,
          cached_tokens: int = 0, cache_write_tokens: int = 0, show_cache: bool = False):
    """Print token usage stats."""
    if call_cost is not None:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o ${call_cost:.4f}|turn: {turn_in:,}i/{turn_out:,}o ${turn_cost:.4f}|session: {sess_in:,}i/{sess_out:,}o ${sess_cost:.4f}"
    else:
        msg = f"[tokens] call: {call_in:,}i/{call_out:,}o|turn: {turn_in:,}i/{turn_out:,}o|session: {sess_in:,}i/{sess_out:,}o"
    print(c('blue', msg))
    if show_cache:
        if cache_write_tokens or cached_tokens:
            print(c('blue', f"[cache] wrote {cache_write_tokens:,} tokens, hit {cached_tokens:,} tokens"))
        else:
            print(c('blue', f"[cache] no cache activity"))


def config_error():
    """Print API key configuration error."""
    print(c('blue', "error: OPENROUTER_API_KEY not set"))
    print(c('blue', "create a .env file with:"))
    print(c('blue', "  OPENROUTER_API_KEY=your_key_here"))


def banner(name: str, model: str):
    """Print startup banner."""
    print(f"{COLORS.get('lavender', '')}{name} [{model}]{COLORS['reset']}")


def model_list(models):
    """Print list of models with pricing."""
    print(c('blue', "Models (current model marked with '*'):"))
    for i, (name, prices, is_current) in enumerate(models, 1):
        inp, out = prices[0], prices[1]
        marker = '*' if is_current else ' '
        print(f"  {c('blue', f'{marker}{i}. {name} ${inp:.2f}/${out:.2f}')}")
    print(c('blue', '\n  /model <n> to switch'))


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
