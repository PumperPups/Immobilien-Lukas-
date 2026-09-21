"""Minimaler HTML-Extraktor auf Basis von html.parser (keine Fremdpakete).

Sucht Inseratsbloecke (z.B. <article data-adid="...">) und sammelt darin
Texte anhand von CSS-Klassenfragmenten ein.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class ListingParser(HTMLParser):
    """Zerlegt eine Suchergebnisseite in Inseratsbloecke.

    :param item_tag: Tag des Blocks, z.B. ``article``
    :param item_attr: Attribut, das einen Block markiert, z.B. ``data-adid``
    :param capture: {Feldname: Klassenfragment}
    """

    def __init__(self, item_tag: str, item_attr: str, capture: dict[str, str]):
        super().__init__(convert_charrefs=True)
        self.item_tag = item_tag
        self.item_attr = item_attr
        self.capture = capture
        self.items: list[dict[str, str]] = []
        self._depth = 0
        self._item_depth: int | None = None
        self._current: dict[str, str] | None = None
        self._active: list[tuple[int, str]] = []   # (depth, feldname)

    # --- HTMLParser-Hooks ---

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        void = tag in VOID_TAGS
        if not void:
            self._depth += 1

        if self._current is None:
            if tag == self.item_tag and self.item_attr in attr:
                self._current = {"id": attr[self.item_attr]}
                if attr.get("data-href"):
                    self._current["href"] = attr["data-href"]
                self._item_depth = self._depth
            return

        classes = attr.get("class", "")
        for key, needle in self.capture.items():
            if needle in classes and key not in self._current:
                self._current[key] = ""
                self._active.append((self._depth, key))
        if tag == "a" and attr.get("href") and "href" not in self._current:
            self._current["href"] = attr["href"]

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if self._current is not None:
            self._active = [(d, k) for d, k in self._active if d < self._depth]
            if self._item_depth == self._depth:
                item = {k: clean(v) for k, v in self._current.items()}
                self.items.append(item)
                self._current = None
                self._item_depth = None
                self._active = []
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._current is None or not data.strip():
            return
        for _, key in self._active:
            self._current[key] = f"{self._current[key]} {data}"


def parse_listings(
    html: str, item_tag: str, item_attr: str, capture: dict[str, str]
) -> list[dict[str, str]]:
    parser = ListingParser(item_tag, item_attr, capture)
    parser.feed(html)
    parser.close()
    return parser.items
