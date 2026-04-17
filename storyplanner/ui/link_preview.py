"""Shared link preview widget — renders [[Entity Name]] as clickable links."""

import re
from collections.abc import Callable
from urllib.parse import quote, unquote

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser

LINK_PATTERN = re.compile(r"\[\[(.+?)\]\]")
LINK_SCHEME = "storylink"


def render_linked_text(plain_text: str) -> str:
    if not plain_text:
        return ""

    def _replace(match: re.Match) -> str:
        name = match.group(1)
        encoded = quote(name, safe="")
        escaped = _esc(name)
        return (
            f'<a href="{LINK_SCHEME}://{encoded}"'
            f' style="color: #1976d2;">{escaped}</a>'
        )

    escaped_text = _esc_except_links(plain_text)
    return escaped_text.replace("\n", "<br>")


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _esc_except_links(text: str) -> str:
    parts: list[str] = []
    last_end = 0
    for match in LINK_PATTERN.finditer(text):
        parts.append(_esc(text[last_end:match.start()]))
        name = match.group(1)
        encoded = quote(name, safe="")
        escaped = _esc(name)
        parts.append(
            f'<a href="{LINK_SCHEME}://{encoded}"'
            f' style="color: #1976d2;">{escaped}</a>'
        )
        last_end = match.end()
    parts.append(_esc(text[last_end:]))
    return "".join(parts)


def create_link_browser(
    on_link_clicked: Callable[[str], None],
    max_height: int = 80,
) -> QTextBrowser:
    browser = QTextBrowser()
    browser.setMaximumHeight(max_height)
    browser.setOpenLinks(False)
    browser.setStyleSheet(
        "QTextBrowser { background: #f9f9f9; border: 1px solid #e0e0e0; }"
    )

    def _handle_click(url: QUrl) -> None:
        if url.scheme() == LINK_SCHEME:
            name = unquote(url.host())
            on_link_clicked(name)

    browser.anchorClicked.connect(_handle_click)
    return browser
