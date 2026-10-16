"""A tiny Markdown-to-HTML renderer for RULES.md (maintainer-owned).

CI installs dependencies from main's requirements.txt only, so the pages avoid a
Markdown package. Supported: headings, paragraphs, blockquotes, `-`/`1.` lists
nested by indentation, pipe tables, **bold**, `code` and [links](url).
"""

from __future__ import annotations

import re
from html import escape

_LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{escape(part[1:-1])}</code>")
            continue
        part = escape(part, quote=False)
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{escape(m[2])}">{m[1]}</a>', part)
        out.append(part)
    return "".join(out)


def _list(lines: list[str]) -> str:
    """Render consecutive list lines; deeper-indented items become a nested list."""
    html: list[str] = []
    stack: list[tuple[int, str]] = []  # (indent, tag)
    for line in lines:
        m = _LIST_ITEM.match(line)
        indent, tag, text = len(m[1]), "ol" if m[2][0].isdigit() else "ul", m[3]
        while stack and indent < stack[-1][0]:
            html.append(f"</li></{stack.pop()[1]}>")
        if stack and indent == stack[-1][0]:
            html.append("</li>")
        else:
            html.append(f"<{tag}>")
            stack.append((indent, tag))
        html.append(f"<li>{inline(text)}")
    while stack:
        html.append(f"</li></{stack.pop()[1]}>")
    return "".join(html)


def _table(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    head, body = rows[0], rows[2:]
    thead = "".join(f"<th>{inline(c)}</th>" for c in head)
    tbody = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in body)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def render(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif m := re.match(r"^(#{1,6})\s+(.*)$", line):
            level = len(m[1])
            out.append(f"<h{level}>{inline(m[2])}</h{level}>")
            i += 1
        elif _LIST_ITEM.match(line):
            start = i
            while i < len(lines) and _LIST_ITEM.match(lines[i]):
                i += 1
            out.append(_list(lines[start:i]))
        elif line.lstrip().startswith("|"):
            start = i
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                i += 1
            out.append(_table(lines[start:i]))
        elif line.startswith(">"):
            start = i
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            quote = " ".join(item.lstrip("> ").strip() for item in lines[start:i])
            out.append(f"<blockquote><p>{inline(quote)}</p></blockquote>")
        else:
            start = i
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|>|\s*\||\s*([-*]|\d+\.)\s)", lines[i]):
                i += 1
            out.append(f"<p>{inline(' '.join(item.strip() for item in lines[start:i]))}</p>")
    return "\n".join(out)
