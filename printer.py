"""Print formatting and colors for cody"""

import difflib
import re

SNIPPET_LEN = 80

# ANSI 256-color codes
COLORS = {
    "reset": "\033[0m",
    "blue": "\033[38;5;75m",
    "lavender": "\033[38;5;183m",
    "dim": "\033[48;5;233m\033[38;5;23m",      # dark grey bg, teal text
    "highlight": "\033[48;5;23m\033[38;5;255m", # teal bg, white text
    "del_hl": "\033[48;5;236m\033[38;5;23m",    # slightly lighter grey bg, same teal text (changed chars on - lines)
    "add_hl": "\033[48;5;236m\033[38;5;183m",   # slightly lighter grey bg, same lavender text (changed chars on + lines)
}

def c(color: str, text: str) -> str:
    """Wrap text in color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def _edit_file_preview(args: dict):
    """Print edit_file preview with context and diff."""
    path = args.get('path', '')
    old_string = args.get('old_string', '')
    new_string = args.get('new_string', '')

    print(f"{c('blue', '[edit_file]')} {c('blue', path)}")

    # Append-only: no old_string
    if not old_string:
        for line in new_string.splitlines()[:5]:
            print(f"  {c('lavender', f'     +  {line[:SNIPPET_LEN]}')}")
        extra = new_string.count('\n') + 1 - 5
        if extra > 0:
            print(f"  {c('blue', f'     ... +{extra} more lines')}")
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the target occurrence (1-indexed, default first)
        occurrence = args.get('occurrence', 1) or 1
        idx, search_start = -1, 0
        for _ in range(occurrence):
            idx = content.find(old_string, search_start)
            if idx == -1:
                break
            search_start = idx + 1

        if idx == -1:
            # old_string not in file — just show raw strings
            _show_diff_lines(old_string.splitlines(), new_string.splitlines())
            return

        start_line = content[:idx].count('\n') + 1  # 1-indexed
        new_content = content[:idx] + new_string + content[idx + len(old_string):]

        _show_unified_diff(content, new_content, start_line)

    except Exception as e:
        print(c('blue', f'  (preview unavailable: {e})'))
        _show_diff_lines(old_string.splitlines(), new_string.splitlines())


def _tokenize(text: str) -> list[str]:
    """Split a line into word/non-word tokens, preserving all characters."""
    return re.findall(r'\w+|\W+', text)


def _intra_line_highlight(old_text: str, new_text: str) -> tuple[str, str]:
    """Return (old_rendered, new_rendered) with intra-line changed spans highlighted.

    Diffs at the token (word) level. For a 1-to-1 word replacement where the two
    words are similar enough, drops down to char-level to highlight only the changed
    characters. Otherwise the whole changed token is highlighted as a unit.

    Unchanged tokens use the base color ('dim' / 'lavender').
    Changed tokens use the highlight color ('del_hl' / 'add_hl').
    """
    old_tokens = _tokenize(old_text)
    new_tokens = _tokenize(new_text)
    sm = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    old_out, new_out = [], []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = old_tokens[i1:i2]
        new_chunk = new_tokens[j1:j2]
        if tag == 'equal':
            old_out.append(c('dim', ''.join(old_chunk)))
            new_out.append(c('lavender', ''.join(new_chunk)))
        else:
            # Any change (replace/insert/delete) — highlight the whole token as a unit
            for tok in old_chunk:
                old_out.append(c('del_hl', tok))
            for tok in new_chunk:
                new_out.append(c('add_hl', tok))

    return ''.join(old_out), ''.join(new_out)


def _render_changed_pairs(minus_lines: list[str], plus_lines: list[str]) -> list[str]:
    """Pair up - and + lines and apply intra-line highlighting. Returns ready-to-print strings."""
    out = []
    pairs = min(len(minus_lines), len(plus_lines))
    for i in range(pairs):
        old_hl, new_hl = _intra_line_highlight(minus_lines[i], plus_lines[i])
        out.append(f"  {c('dim', '     -  ')}{old_hl}")
        out.append(f"  {c('lavender', '     +  ')}{new_hl}")
    # Any unmatched leftover lines (length mismatch) get plain coloring
    for line in minus_lines[pairs:]:
        out.append(f"  {c('dim', f'     -  {line[:SNIPPET_LEN]}')}")
    for line in plus_lines[pairs:]:
        out.append(f"  {c('lavender', f'     +  {line[:SNIPPET_LEN]}')}")
    return out


def _show_unified_diff(old_content: str, new_content: str, start_line: int, context: int = 2):
    """Render a compact unified diff of the changed region, capped at max_lines shown."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    hunks = list(difflib.unified_diff(
        old_lines, new_lines,
        n=context, lineterm='',
    ))
    if not hunks:
        print(f"  {c('blue', '(no changes)')}")
        return

    # First pass: collect hunk lines, grouping consecutive - and + runs for pairing
    # We buffer pending minus lines, then flush when we hit a non-plus line.
    shown = 0
    max_lines = 20
    pending_minus: list[str] = []
    pending_plus: list[str] = []

    def flush_pending():
        nonlocal shown
        for rendered in _render_changed_pairs(pending_minus, pending_plus):
            if shown >= max_lines:
                return
            print(rendered)
            shown += 1
        pending_minus.clear()
        pending_plus.clear()

    for line in hunks[2:]:  # skip --- / +++ header lines
        if shown >= max_lines:
            print(f"  {c('blue', '     ... diff truncated')}")
            break
        tag, text = line[0], line[1:].rstrip()
        if tag == '-':
            # Flush any accumulated plus lines first (shouldn't normally happen in unified diff,
            # but be safe), then buffer this minus line
            if pending_plus:
                flush_pending()
            pending_minus.append(text)
        elif tag == '+':
            pending_plus.append(text)
        else:
            flush_pending()
            if shown >= max_lines:
                print(f"  {c('blue', '     ... diff truncated')}")
                break
            if tag == '@':
                try:
                    hunk_info = line.split('@@')[1].strip()
                    old_start = int(hunk_info.split()[0].lstrip('-').split(',')[0])
                    new_start = int(hunk_info.split()[1].lstrip('+').split(',')[0])
                    offset = start_line - 1
                    print(c('blue', f'  @@ -{old_start + offset} +{new_start + offset} @@'))
                except Exception:
                    print(c('blue', f'  {line.rstrip()}'))
            else:
                print(f"  {c('blue', f'        {text[:SNIPPET_LEN]}')}")
            shown += 1

    flush_pending()


def _show_diff_lines(old_lines: list[str], new_lines: list[str]):
    """Fallback: just show - / + lines without file context."""
    for rendered in _render_changed_pairs(old_lines[:10], new_lines[:10]):
        print(rendered)


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
