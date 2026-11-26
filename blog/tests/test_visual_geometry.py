"""Diagram rendering rejects arrowheads that enter boxes and separates edge labels."""
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_short_connector_is_detected_before_rasterizing():
    script = r"""
import {visualCollisions, downwardArrowheadBox} from './scripts/visual_geometry.mjs';
const boxes = [
  {id:'top', x:0, y:0, width:100, height:100},
  {id:'bottom', x:0, y:125, width:100, height:100},
];
const frame = {nodes:boxes, title:{id:'title',x:0,y:-100,width:100,height:30},
  footer:{id:'footer',x:0,y:400,width:100,height:30}};
const bad = visualCollisions({...frame, arrowheads:[
  {id:'arrow', ...downwardArrowheadBox(50,113)}]});
const good = visualCollisions({...frame, nodes:[boxes[0], {...boxes[1], y:200}],
  arrowheads:[{id:'arrow', ...downwardArrowheadBox(50,188)}]});
process.stdout.write(JSON.stringify({bad,good}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=ROOT,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert "arrow overlaps top" in report["bad"]
    assert report["good"] == []


def test_labeled_edge_gets_room_for_arrowhead(tmp_path):
    def render(edge_label):
        visual = {
            "id": "geometry-test", "type": "process", "language": "en",
            "title": "Two steps", "alt": "Two connected steps",
            "data": {
                "nodes": [{"id": "first", "label": "First step"},
                          {"id": "second", "label": "Second step"}],
                "edges": [{"from": "first", "to": "second", "label": edge_label}],
            },
        }
        output = tmp_path / f"{edge_label or 'plain'}.png"
        result = subprocess.run(
            ["node", str(ROOT / "scripts/visual_renderer.mjs"), str(output)],
            cwd=ROOT, input=json.dumps(visual), capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["height"]

    assert render("Then") - render("") >= 60
