"""ISW "Russian Offensive Campaign Assessment" daily reports (text).

Reports are mirrored on criticalthreats.org with a stable slug:
  /analysis/russian-offensive-campaign-assessment-{month}-{d}-{yyyy}
(understandingwar.org carries the same report; its URL scheme has changed over
time, so the mirror is the default and the base is configurable.)

Parsing goal: (heading, paragraphs) sections + numbered endnotes -> URLs, so
extracted observations can cite ISW's own sources. Headings in the "frontline"
part name operational directions ("Kupyansk direction", "Pokrovsk direction"),
which become each observation's `axis`.

Copyright: store the text locally for extraction only. The app shows our own
paraphrase plus a <=25-word excerpt and a deep link — never the report body.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..timeutil import day_index, day_to_date
from .base import Document, Section, get_text, http_client, save_raw

BASE = "https://www.criticalthreats.org/analysis/"
FOOTNOTE_RE = re.compile(r"^\s*\[(\d+)\]\s*(.*)$", re.S)
URL_RE = re.compile(r"https?://\S+")
# Endnotes block typically starts after a paragraph that is only "[1] ..." lines.
CONTENT_SELECTORS = ["article .content", "article", "main", "body"]


def report_url(day: int, base: str = BASE) -> str:
    d = day_to_date(day)
    return f"{base}russian-offensive-campaign-assessment-{d.strftime('%B').lower()}-{d.day}-{d.year}"


def parse_report(html: str, url: str, day: int) -> Document:
    tree = HTMLParser(html)
    root = None
    for sel in CONTENT_SELECTORS:
        root = tree.css_first(sel)
        if root is not None:
            break
    assert root is not None
    title_node = tree.css_first("h1") or tree.css_first("title")
    title = title_node.text(strip=True) if title_node else ""

    sections: list[Section] = [Section("", [])]
    footnotes: dict[str, list[str]] = {}
    for node in root.traverse(include_text=False):
        tag = node.tag
        if tag in ("h2", "h3", "h4") or (tag == "p" and _is_bold_heading(node)):
            sections.append(Section(node.text(strip=True), []))
            continue
        if tag != "p":
            continue
        text = node.text(separator=" ", strip=True)
        if not text:
            continue
        m = FOOTNOTE_RE.match(text)
        if m and URL_RE.search(m.group(2)):
            footnotes[m.group(1)] = URL_RE.findall(m.group(2))
            continue
        sections[-1].paragraphs.append(text)
    sections = [s for s in sections if s.paragraphs]
    return Document(
        source_id="isw",
        url=url,
        day=day,
        published_at=None,
        title=title,
        language="en",
        sections=sections,
        footnotes=footnotes,
    )


def _is_bold_heading(node) -> bool:  # ISW sometimes uses <p><strong>Heading</strong></p>
    kids = [c for c in node.iter(include_text=False)]
    return len(kids) == 1 and kids[0].tag in ("strong", "b") and len(node.text(strip=True)) < 120


class IswReportSource:
    source_id = "isw"

    def __init__(self, base: str = BASE):
        self.base = base

    def documents(self, day_from: int, day_to: int) -> Iterator[Document]:
        with http_client() as c:
            for day in range(day_from, day_to + 1):
                url = report_url(day, self.base)
                try:
                    html = get_text(c, url)
                except Exception:  # ISW skips some days (holidays); not an error
                    continue
                save_raw(self.source_id, f"reports/{day_to_date(day).isoformat()}.html", html)
                doc = parse_report(html, url, day)
                doc.published_at = datetime.now(UTC)
                yield doc


__all__ = ["IswReportSource", "parse_report", "report_url", "day_index"]
