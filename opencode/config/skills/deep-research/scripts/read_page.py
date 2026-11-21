#!/usr/bin/env python3
"""
Lightweight, resilient page reader, HTML text extractor, and table converter
for deep-research. Uses only Python standard library.
Preserves structured HTML tables into Markdown format for quantitative benchmarks,
specs, clinical trial results, and financial reports.
"""

import gzip
import html
import re
import ssl
import urllib.error
import urllib.request
import zlib
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "max-age=0",
}


class HTMLTableParser(HTMLParser):
    """
    Parses HTML table elements (table, tr, th, td) into a list of 2D string matrices.
    Resilient to malformed HTML, nested tags, and unclosed cells.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: List[List[List[str]]] = []
        self._table_stack: List[Tuple[Any, Any, Any, bool]] = []
        self._current_table: Optional[List[List[str]]] = None
        self._current_row: Optional[List[str]] = None
        self._current_cell: Optional[List[str]] = None
        self._in_cell: bool = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._current_table is not None:
                self._table_stack.append(
                    (self._current_table, self._current_row, self._current_cell, self._in_cell)
                )
            self._current_table = []
            self._current_row = None
            self._current_cell = None
            self._in_cell = False
        elif tag == "tr":
            if self._current_table is not None:
                self._close_current_row()
                self._current_row = []
        elif tag in ("th", "td"):
            if self._current_row is not None:
                self._close_current_cell()
                self._current_cell = []
                self._in_cell = True

    def _close_current_cell(self) -> None:
        if self._current_row is not None and self._current_cell is not None:
            cell_text = "".join(self._current_cell).strip()
            self._current_row.append(cell_text)
            self._current_cell = None
            self._in_cell = False

    def _close_current_row(self) -> None:
        self._close_current_cell()
        if self._current_table is not None and self._current_row is not None:
            if any(cell.strip() for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("th", "td"):
            self._close_current_cell()
        elif tag == "tr":
            self._close_current_row()
        elif tag == "table":
            self._close_current_row()
            if self._current_table and len(self._current_table) > 0:
                self.tables.append(self._current_table)
            if self._table_stack:
                self._current_table, self._current_row, self._current_cell, self._in_cell = (
                    self._table_stack.pop()
                )
            else:
                self._current_table = None

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._current_cell is not None:
            self._current_cell.append(data)


def table_to_markdown(grid: List[List[str]]) -> str:
    """
    Converts a 2D matrix of strings into a standardized GitHub Flavored Markdown table.
    Escapes pipe characters in cells and ensures uniform column widths.
    """
    if not grid:
        return ""

    valid_rows = [r for r in grid if any(cell.strip() for cell in r)]
    if not valid_rows:
        return ""

    num_cols = max(len(r) for r in valid_rows)
    # Require at least 2 columns or 2 rows for meaningful tabular data
    if num_cols < 2 and len(valid_rows) < 2:
        return ""

    norm_rows: List[List[str]] = []
    for r in valid_rows:
        row_cells = []
        for c in r:
            cleaned = re.sub(r"\s+", " ", html.unescape(c)).strip()
            # Escape pipes inside markdown cells
            cleaned = cleaned.replace("|", r"\|")
            row_cells.append(cleaned)
        if len(row_cells) < num_cols:
            row_cells.extend([""] * (num_cols - len(row_cells)))
        norm_rows.append(row_cells[:num_cols])

    header = norm_rows[0]
    separators = ["---"] * num_cols
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(separators) + "|",
    ]
    for row in norm_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def html_to_markdown_tables(raw_html: str, max_tables: int = 10) -> List[str]:
    """
    Parses HTML content and extracts up to max_tables clean Markdown tables.
    """
    if not raw_html or not isinstance(raw_html, str) or "<table" not in raw_html.lower():
        return []

    parser = HTMLTableParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception:
        # Fallback to regex-based extraction if parser encounters catastrophic error
        return _regex_fallback_tables(raw_html, max_tables)

    md_tables: List[str] = []
    for grid in parser.tables:
        md = table_to_markdown(grid)
        if md:
            md_tables.append(md)
            if len(md_tables) >= max_tables:
                break

    return md_tables


def _regex_fallback_tables(raw_html: str, max_tables: int = 10) -> List[str]:
    """Fallback regex extractor for heavily corrupted HTML."""
    table_pattern = r"<table[^>]*>(.*?)</table>"
    row_pattern = r"<tr[^>]*>(.*?)</tr>"
    cell_pattern = r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>"

    results: List[str] = []
    for tbl_match in re.finditer(table_pattern, raw_html, flags=re.DOTALL | re.IGNORECASE):
        grid: List[List[str]] = []
        for row_match in re.finditer(row_pattern, tbl_match.group(1), flags=re.DOTALL | re.IGNORECASE):
            cells = [
                re.sub(r"<[^>]+>", " ", c.group(1)).strip()
                for c in re.finditer(cell_pattern, row_match.group(1), flags=re.DOTALL | re.IGNORECASE)
            ]
            if cells:
                grid.append(cells)
        md = table_to_markdown(grid)
        if md:
            results.append(md)
            if len(results) >= max_tables:
                break
    return results


def extract_title_from_html(raw_html: str) -> str:
    """
    Extracts the document title from <title> or <meta property="og:title">.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""

    m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.DOTALL | re.IGNORECASE)
    if m:
        t = re.sub(r"<[^>]+>", " ", m.group(1))
        t = html.unescape(t).strip()
        t = re.sub(r"\s+", " ", t)
        if t:
            return t

    m = re.search(r"""<meta\s+[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']""", raw_html, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"""<meta\s+[^>]*content=["']([^"']+)["'][^>]*property=["']og:title["']""", raw_html, flags=re.IGNORECASE)
    if m:
        t = html.unescape(m.group(1)).strip()
        t = re.sub(r"\s+", " ", t)
        if t:
            return t

    return ""


def clean_html(raw_html: str) -> str:
    """
    Strips <script>, <style>, boilerplate tags, unescapes entities,
    and collapses excessive whitespace while keeping paragraph and table breaks.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""

    text = raw_html

    # Strip script, style, noscript, svg, nav, footer, and comments
    noise_patterns = [
        r"<script[^>]*>.*?</script>",
        r"<style[^>]*>.*?</style>",
        r"<noscript[^>]*>.*?</noscript>",
        r"<svg[^>]*>.*?</svg>",
        r"<!--.*?-->",
        r"<nav[^>]*>.*?</nav>",
        r"<footer[^>]*>.*?</footer>",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert structural block tags to newlines
    block_tags = [
        r"</p>", r"</div>", r"</li>", r"</tr>",
        r"</h1>", r"</h2>", r"</h3>", r"</h4>", r"</h5>", r"</h6>",
        r"<br\s*/?>", r"<hr\s*/?>",
    ]
    for tag in block_tags:
        text = re.sub(tag, "\n", text, flags=re.IGNORECASE)

    # Convert table cell endings to spaces so words don't merge
    text = re.sub(r"</(?:td|th)>", " ", text, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Unescape HTML entities (&amp;, &quot;, &#x27;, etc.)
    text = html.unescape(text)

    # Normalize horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Clean up spaces before punctuation caused by inline tag stripping
    text = re.sub(r" ([,\.!?;:])", r"\1", text)

    # Collapse excessive vertical whitespace (max 2 consecutive newlines)
    lines = [line.strip() for line in text.split("\n")]
    cleaned_lines = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned_lines.append("")
                prev_blank = True
        else:
            cleaned_lines.append(line)
            prev_blank = False

    return "\n".join(cleaned_lines).strip()


def fetch_raw_page(url: str, timeout: float = 6.0) -> Tuple[str, str, bool]:
    """
    Resilient HTTP fetcher with decompression (gzip, deflate), charset detection,
    redirect following, and SSL fallback.
    Returns: (raw_html, content_type, success)
    """
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return "", "", False

    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)

    # Try standard default context first
    context = ssl.create_default_context()
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                content_type = response.headers.get("Content-Type", "")
                content_encoding = response.headers.get("Content-Encoding", "").lower()

                # Read raw bytes (limit to ~2MB)
                raw_bytes = response.read(2 * 1024 * 1024)

                # Handle gzip / deflate compression
                if "gzip" in content_encoding:
                    try:
                        raw_bytes = gzip.decompress(raw_bytes)
                    except Exception:
                        pass
                elif "deflate" in content_encoding:
                    try:
                        raw_bytes = zlib.decompress(raw_bytes)
                    except Exception:
                        try:
                            raw_bytes = zlib.decompress(raw_bytes, -zlib.MAX_WBITS)
                        except Exception:
                            pass

                # Detect charset
                charset = None
                if "charset=" in content_type.lower():
                    m = re.search(r"charset=([a-zA-Z0-9_\-]+)", content_type, re.IGNORECASE)
                    if m:
                        charset = m.group(1).lower()

                if not charset:
                    # Sniff first 2048 bytes for meta charset
                    head_sample = raw_bytes[:2048].decode("ascii", errors="ignore")
                    m = re.search(r"""<meta\s+[^>]*charset=["']?([a-zA-Z0-9_\-]+)""", head_sample, re.IGNORECASE)
                    if m:
                        charset = m.group(1).lower()

                if not charset:
                    charset = "utf-8"

                try:
                    raw_html = raw_bytes.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    try:
                        raw_html = raw_bytes.decode("utf-8", errors="replace")
                    except Exception:
                        raw_html = raw_bytes.decode("latin-1", errors="replace")

                return raw_html, content_type, True

        except (ssl.SSLError, urllib.error.URLError) as e:
            if attempt == 0 and "CERTIFICATE_VERIFY_FAILED" in str(e):
                # Fallback to unverified SSL context for research scraping
                context = ssl._create_unverified_context()
                continue
            return "", "", False
        except Exception:
            return "", "", False

    return "", "", False


def extract_page_content_summary(
    url: str,
    max_chars: int = 12000,
    timeout: float = 6.0
) -> Dict[str, Any]:
    """
    Fetches URL and extracts full clean narrative text and structured Markdown tables.
    Returns:
    {
        "url": url,
        "title": title,
        "text": text,
        "tables": [md_table_strings],
        "success": bool
    }
    """
    empty_result = {
        "url": url,
        "title": "",
        "text": "",
        "tables": [],
        "success": False,
    }

    raw_html, content_type, ok = fetch_raw_page(url, timeout=timeout)
    if not ok or not raw_html:
        return empty_result

    title = extract_title_from_html(raw_html)
    tables = html_to_markdown_tables(raw_html, max_tables=8)
    clean_text = clean_html(raw_html)

    if max_chars and len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars].rsplit(" ", 1)[0] + "..."

    return {
        "url": url,
        "title": title,
        "text": clean_text,
        "tables": tables,
        "success": True,
    }


def fetch_page_text(url: str, max_chars: int = 15000, timeout: float = 8.0) -> str:
    """
    Safely fetches primary page text if deep text inspection is required.
    Maintains backward compatibility with legacy callers.
    """
    summary = extract_page_content_summary(url, max_chars=max_chars, timeout=timeout)
    if not summary["success"]:
        return ""

    parts = []
    if summary["title"]:
        parts.append(f"# {summary['title']}\n")
    if summary["tables"]:
        parts.append("\n### Structured Tables:\n" + "\n\n".join(summary["tables"]) + "\n")
    if summary["text"]:
        parts.append("### Content:\n" + summary["text"])

    combined = "\n".join(parts)
    return combined[:max_chars]
