"""Chart exports use the documented website palette and font assets."""
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def render_chart(tmp_path: Path, chart_type: str, unit: str = "Example points",
                 axis_max: int | None = None, series_count: int = 1) -> str:
    data = {
        "unit": unit,
        "categories": ["Category A", "Category B", "Category C"],
        "series": [{"name": "Example series", "values": [22, 41, 33]}],
    }
    if series_count > 1:
        data["series"].append({"name": "Second series", "values": [12, 32, 26]})
    if chart_type == "line":
        data["x_label"] = "Example period"
    if axis_max is not None:
        data["axis_max"] = axis_max
        data["axis_suffix"] = "%"
    spec = {"type": chart_type, "title": "SAMPLE DATA", "alt": "Example", "data": data, "language": "en"}
    target = tmp_path / f"{chart_type}.png"
    result = subprocess.run(
        ["node", str(ROOT / "scripts/visual_renderer.mjs"), str(target)],
        input=json.dumps(spec), text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert target.exists()
    return target.with_suffix(".svg").read_text()


def test_chart_legend_moves_below_wrapped_unit_label(tmp_path: Path):
    long_unit = "Percent of surveyed workers with access to an employer-provided benefit in each respondent group"
    for kind in ("bar", "line"):
        short_svg = render_chart(tmp_path, kind, series_count=2)
        long_svg = render_chart(tmp_path, kind, long_unit, series_count=2)
        legend = r'<rect x="56" y="([0-9.]+)" width="30" height="30"'
        short_y = float(re.search(legend, short_svg).group(1))
        long_y = float(re.search(legend, long_svg).group(1))
        assert long_y - short_y >= 38, f"{kind} legend overlaps the wrapped unit label"


def test_single_series_bar_has_no_redundant_legend(tmp_path: Path):
    svg = render_chart(tmp_path, "bar")
    assert not re.search(r'<rect x="56" y="[0-9.]+" width="30" height="30"', svg)
    assert re.search(r'<rect x="56" y="[0-9.]+" width="[0-9.]+" height="36"', svg)


def test_percentage_bars_use_fixed_hundred_percent_axis(tmp_path: Path):
    svg = render_chart(tmp_path, "bar", "Percent of surveyed workers", axis_max=100)
    first_bar = re.search(r'<rect x="56" y="[0-9.]+" width="([0-9.]+)" height="36"', svg)
    assert first_bar, "first data bar is missing"
    assert abs(float(first_bar.group(1)) - 860 * 22 / 100) < 0.01
    assert re.search(r'<path d="M56,[0-9.]+ H916" stroke=', svg), "fixed axis is not visible"


def test_bar_and_line_use_site_palette_and_distinct_site_fonts(tmp_path: Path):
    palette = json.loads((ROOT / "config/site-brand-tokens.json").read_text())
    approved_colors = {
        value for family in palette.values() if isinstance(family, dict) for value in family.values()
    } | {value for value in palette.values() if isinstance(value, str) and value.startswith("#")}
    approved_colors = {value.lower() for value in approved_colors}

    font_paths = subprocess.run(
        ["node", "--input-type=module", "-e", """
import {createSiteChartFont} from './tools/covers/lib-site-chart-font.mjs';
const dir='./tools/covers/assets';
const heading=createSiteChartFont(dir,'Exo2-SemiBold.ttf');
const body=createSiteChartFont(dir,'Manrope-Regular.ttf');
const strong=createSiteChartFont(dir,'Manrope-SemiBold.ttf');
const path=s=>s.match(/d=\"([^\"]+)/)[1];
process.stdout.write(JSON.stringify({title:path(heading.pathOf('SAMPLE DATA',0,0,50,'#fff')),
  regular:path(body.pathOf('Category A',0,0,40,'#fff')),
  strong:path(strong.pathOf('Category A',0,0,40,'#fff'))}));
"""], cwd=ROOT, text=True, capture_output=True,
    )
    assert font_paths.returncode == 0, font_paths.stderr
    glyphs = json.loads(font_paths.stdout)

    for kind in ("bar", "line"):
        svg = render_chart(tmp_path, kind)
        assert {value.lower() for value in re.findall(r"#[0-9a-fA-F]{6}", svg)} <= approved_colors
        assert glyphs["title"] in svg
        assert glyphs["strong" if kind == "bar" else "regular"] in svg
