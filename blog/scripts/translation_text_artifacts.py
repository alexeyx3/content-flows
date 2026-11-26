"""Find leaked tool/chat markup in publication text; never rewrite the input.

This is a technical cleanliness check, not an AI-authorship detector. Ordinary
words, prose style, tracking parameters and Unicode joiners are not findings.
"""
from __future__ import annotations

import html
import re


PATTERNS = (
    ('oai_citation', re.compile(r'\boai_citation\b', re.I)),
    ('contentReference', re.compile(r':contentReference\s*\[\s*oaicite\s*:', re.I)),
    ('source citation token', re.compile(r'【\s*\d+\s*†[^】\n]+】')),
    ('cite token', re.compile(r'\[cite:\s*\d+\s*\]', re.I)),
    ('span token', re.compile(r'\[span_\d+\]', re.I)),
    ('sandbox artifact path', re.compile(r'sandbox:/mnt/data(?:[/\s)\]"\'>]|$)', re.I)),
    ('think closing tag', re.compile(r'</think\s*>', re.I)),
)


def findings(value: str) -> list[dict]:
    """Return marker names/lines, including markup encoded as HTML entities."""
    text = html.unescape(value)
    result = []
    for name, pattern in PATTERNS:
        for match in pattern.finditer(text):
            result.append({'marker': name, 'line': text.count('\n', 0, match.start()) + 1})
    return result


def errors(fields: dict[str, str], source_fields: dict[str, str]) -> list[str]:
    """Source-carried tokens remain explicit source-policy conflicts, not edits."""
    result = []
    for field, value in fields.items():
        source_markers = {item['marker'] for item in findings(source_fields.get(field, ''))}
        for item in findings(value):
            message = (f"technical text artifact in {field} at line {item['line']}: "
                       + item['marker'])
            if item['marker'] in source_markers:
                message += '; also present in immutable source; source-policy review required'
            result.append(message)
    return result
