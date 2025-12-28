"""Web tools: fetch pages and search."""

from . import tool


def _get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
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


def _fetch_with_browser(url: str) -> str:
    from playwright.sync_api import sync_playwright

    print("[browser] launching playwright firefox", end="", flush=True)
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = context.new_page()
        page.goto(url, timeout=30000, wait_until="load")
        text = page.inner_text("body")
        browser.close()
    print(" done")
    return text


def _fetch_with_requests(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    response = session.get(url, timeout=15, headers=_get_headers())
    response.raise_for_status()
    print(f"[requests] status={response.status_code}, parsing...", end="", flush=True)

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    print(" done")
    return text


def _process_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)
    print(f"{len(lines)} lines, {len(text)} chars")
    return text


@tool(
    name="fetch_webpage",
    description="Fetch a webpage and extract its text content. Use use_browser=true for JavaScript-heavy sites.",
    params={
        "url": "The URL to fetch",
        "use_browser": {"type": "boolean", "description": "Use headless browser (Playwright) for JS-rendered content. Default: false"}
    },
    required=["url"]
)
def fetch_webpage(url: str, use_browser: bool = False, session=None) -> str:
    try:
        if use_browser:
            text = _fetch_with_browser(url)
            return _process_text(text)

        # Try requests first, fall back to browser on failure
        try:
            text = _fetch_with_requests(url)
            return _process_text(text)
        except Exception as req_err:
            print(f"{req_err}")
            print("retrying with playwright firefox")
            try:
                text = _fetch_with_browser(url)
                return _process_text(text)
            except Exception as browser_err:
                print(f"playwright failed: {browser_err}")
                return f"error fetching {url}: requests failed ({req_err}), browser also failed ({browser_err})"
    except Exception as e:
        print(f"{e}")
        return f"error fetching {url}: {e}"


@tool(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets of search results.",
    params={"query": "The search query"},
    required=["query"]
)
def web_search(query: str, session=None) -> str:
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
            return "No search results found."

        return "\n\n".join(results)
    except Exception as e:
        print(f"error: {e}")
        return f"Error searching: {e}"
