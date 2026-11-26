"""Future enacted/announced rates must not look like historical observations."""
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

RENDERER = Path(__file__).resolve().parents[1] / "vendor/blog/scripts/visual_renderer.mjs"
NS = {"s": "http://www.w3.org/2000/svg"}


@pytest.mark.parametrize("announced", [None, 1, 2])
def test_future_segment_and_markers_are_distinct(tmp_path, announced):
    series = {"name": "Monthly minimum", "values": [100, 110, 120]}
    if announced is not None:
        series["announced_from_index"] = announced
    visual = {"type": "line", "title": "Minimum wage", "alt": "Three annual values",
              "language": "en", "data": {"unit": "EUR", "x_label": "Year",
              "categories": ["2025", "2026", "2027"], "series": [series]}}
    output = tmp_path / "line.png"
    result = subprocess.run(["node", str(RENDERER), str(output)], input=json.dumps(visual),
                            text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)["width"] == 1200
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    root = ET.parse(output.with_suffix(".svg")).getroot()
    lines = root.findall("s:polyline", NS)
    circles = root.findall("s:circle", NS)
    if announced is None:
        assert len(lines) == 1 and "stroke-dasharray" not in lines[0].attrib
        assert len(lines[0].get("points").split()) == 3
        assert len(circles) == 3 and all(c.get("fill") == "#F2B544" for c in circles)
    else:
        assert len(lines) == 2
        assert "stroke-dasharray" not in lines[0].attrib
        assert lines[1].get("stroke-dasharray") == "12 9"
        assert len(lines[0].get("points").split()) == announced
        assert len(lines[1].get("points").split()) == 4 - announced
        assert lines[0].get("points").split()[-1] == lines[1].get("points").split()[0]
        points = circles[-3:]  # First circle is the announced-status legend sample.
        assert all(c.get("fill") == "#F2B544" for c in points[:announced])
        assert all(c.get("fill") == "#101216" and c.get("stroke") == "#F2B544"
                   for c in points[announced:])
