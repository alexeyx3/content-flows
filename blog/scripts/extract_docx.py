"""Extract plain text from a .docx using only the standard library."""
from __future__ import annotations
import sys, zipfile, re
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    root = ET.fromstring(xml)
    lines = []
    for para in root.iter(f"{W}p"):
        text = "".join(node.text or "" for node in para.iter(f"{W}t"))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(docx_to_text(src), encoding="utf-8")
    print(f"{src.name} -> {out} ({out.stat().st_size} bytes)")
