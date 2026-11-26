"""Network-free checks for concurrent SERP card collection."""
import importlib.util
import threading
from pathlib import Path


def test_parallel_fetch_keeps_order_and_failed_cards(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "vendor/blog/scripts/build_article_serp_brief.py"
    spec = importlib.util.spec_from_file_location("serp_cards_parallel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    barrier = threading.Barrier(3)
    seen = []
    lock = threading.Lock()

    def fake_card(row, timeout):
        with lock:
            seen.append(row["url"])
        barrier.wait(timeout=5)
        return {"url": row["url"], "status": "error" if row["url"] == "b" else "ok"}

    monkeypatch.setattr(module, "build_card", fake_card)
    rows = [{"url": x} for x in ["a", "b", "c"]]
    cards = module.build_cards(rows, timeout=1, sleep_seconds=0, workers=3)
    assert sorted(seen) == ["a", "b", "c"]
    assert [c["url"] for c in cards] == ["a", "b", "c"]
    assert cards[1]["status"] == "error"
