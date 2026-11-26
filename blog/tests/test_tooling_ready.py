"""Tools without which the blog track cannot run."""
import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NEEDED = [
    "md_to_gdoc.py", "fetch_gdoc_tabs.py", "check_links.py", "text_overlap.py",
    "wordcount.py", "package_article.py", "validate_codex_setup.py",
]


def test_scripts_present_and_parse():
    for name in NEEDED:
        p = ROOT / "scripts" / name
        assert p.exists(), f"script {name} is missing"
        ast.parse(p.read_text(encoding="utf-8"))


def test_service_account_key_present():
    key = ROOT / "config" / "google-service-account.json"
    if not key.exists():
        pytest.skip("config/google-service-account.json is absent in the template; Drive/Docs/Sheets need it at run time")
    assert key.exists()


def test_service_account_key_is_not_committed():
    """The key is a secret. It must live on disk and must NOT enter git."""
    out = subprocess.run(
        ["git", "ls-files", "config/google-service-account.json"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()
    assert out == "", "the service account key entered the git index"


def test_local_secrets_are_not_committed():
    for path in ("config/.env", "config/openrouter.env", "config/strapi-api-token"):
        out = subprocess.run(
            ["git", "ls-files", path], cwd=ROOT, capture_output=True, text=True,
        ).stdout.strip()
        assert out == "", f"a secret entered the git index: {path}"
