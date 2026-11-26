"""The drafter needs not only the rules but also the data to follow them."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate_draft as gd  # noqa: E402

PACK = {"rules": "правила", "brief": "бриф", "evidence": "факты", "cards": "",
        "site_urls": "- https://example.com/countries/ — countries\n- https://example.com/pricing/ — pricing"}


def test_prompt_carries_internal_link_map():
    """The rule "links only from config/site-urls.json" cannot be followed without the list itself:
    the model either places no links or invents an address."""
    p = gd.system_prompt(PACK)
    assert "https://example.com/countries/" in p
    assert "https://example.com/pricing/" in p


def test_prompt_still_carries_the_basics():
    p = gd.system_prompt(PACK)
    for part in ("правила", "бриф", "факты"):
        assert part in p


def test_site_urls_loaded_as_lines():
    """The map is loaded from config/site-urls.json and turned into "address — label" lines."""
    text = gd.site_urls_block()
    assert text.count("https://example.com") >= 20
    assert " — " in text


def test_home_page_is_marked_as_a_bad_link_target():
    """The model takes the first suitable address from the map. Without an explicit ban this is the home page;
    on a first run a draft got six links to it instead of to sections."""
    p = gd.system_prompt(PACK)
    assert "home page" in p.lower()


def test_editor_also_gets_the_link_map():
    """The editor fixes links. Without the map it does not know what to replace the home page with."""
    import edit_draft as ed
    src = Path(ed.__file__).read_text(encoding="utf-8")
    assert "site_urls_block" in src or "site-urls.json" in src


def test_track_rules_reach_the_writer():
    """knowledge/blog-owned.md is the track rules card. It used to reach only the brief
    through the knowledge tools, while the draft and the edit did not see it, so a wrong
    spelling of a term spread through an article even though the rule had been written down."""
    pack = dict(PACK, track_rules="ПРАВИЛА ТРЕКА: аббревиатуры EOR, AOR")
    assert "аббревиатуры EOR, AOR" in gd.system_prompt(pack)


def test_track_rules_loaded_from_knowledge():
    text = gd.track_rules_block()
    assert "blog" in text.lower()
    assert len(text) > 500


def test_editor_gets_track_rules_too():
    import edit_draft as ed
    src = Path(ed.__file__).read_text(encoding="utf-8")
    assert "track_rules_block" in src or "blog-owned.md" in src
