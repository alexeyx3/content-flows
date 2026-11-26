#!/usr/bin/env python3
"""Glossary-only inline adapter for the shared native-image Docs exporter."""
from __future__ import annotations

import importlib.util
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin

import markdown
from glossary_materials import BLOG_V2


class InlineHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ""
        self.spans = []
        self.open = []

    def handle_starttag(self, tag, attrs):
        style = {"strong": "bold", "em": "italic", "code": "code", "a": "link"}.get(tag)
        if style:
            value = urljoin("https://example.com/", dict(attrs).get("href", "")) if tag == "a" else None
            self.open.append((tag, len(self.text), style, value))
        elif tag == "br":
            self.text += "\n"

    def handle_endtag(self, tag):
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:
                _, start, style, value = self.open.pop(i)
                self.spans.append((start, len(self.text), style, value))
                break

    def handle_data(self, data):
        self.text += data


def render_inline(text):
    """Use the same Markdown semantics as the package and text verifier.

    The shared regex exporter leaves root-relative links and code nested in
    bold text literal. HTML-derived overlapping spans retain their formatting
    while resolving site-relative destinations for Google Docs.
    """
    parsed = InlineHTML()
    parsed.feed(markdown.markdown(text))
    return parsed.text, parsed.spans


def main():
    script = BLOG_V2 / "scripts/md_to_gdoc.py"
    sys.path.insert(0, str(script.parent))
    spec = importlib.util.spec_from_file_location("glossary_shared_docs_export", script)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    shared.inline = render_inline
    shared.main()


if __name__ == "__main__":
    main()
