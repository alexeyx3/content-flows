"""Check local workflow dependencies without network access or external writes."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True
from common import BLOG, ROOT  # noqa: E402


CREDENTIALS = {
    ".env": "copy .env.example and fill in the SERP, OpenRouter and Drive values",
    "google-service-account.json": "Google service-account key for Docs and Drive",
    "strapi-api-token": "CMS API token",
}


def check() -> list[str]:
    errors = []
    try:
        routing = json.loads((ROOT / "config/codex-model-routing.json").read_text())
        routes = routing["agents"]
        parent = routing["orchestrator"]
        if parent["reasoning_effort"] != "medium" and routing.get("orchestrator_override", {}).get("allow_high_effort") is not True:
            errors.append("Non-medium orchestrator route requires orchestrator_override.allow_high_effort")
    except (OSError, ValueError, KeyError) as exc:
        errors.append(f"Cannot load model routes: {exc}")
        routes = {}
    required = [
        ROOT / "AGENTS.md", ROOT / ".agents/skills/country-guide/SKILL.md",
        ROOT / "config/guide-execution.json", ROOT / "scripts/guide_api.py",
        ROOT / "scripts/check_cms_country.py",
        ROOT / "docs/api-execution.md",
        ROOT / "knowledge/guides-rules.md", ROOT / "knowledge/facts-schema.md",
        ROOT / "knowledge/product-positioning.md", ROOT / "docs/country-guides-flow.md",
        ROOT / ".agents/skills/humanizer/SKILL.md",
        ROOT / ".agents/skills/copywriter/SKILL.md",
        ROOT / "config/brand-rules.json", ROOT / "config/stop-brands.json", ROOT / "config/vendors.json",
        ROOT / "config/queue.json", ROOT / "config/geos.json", ROOT / "config/site-links.json",
        BLOG / "config/blog-authors.json",
        BLOG / "tools/sanitize/check.js", BLOG / "tools/sanitize/node_modules/sanitize-html/package.json",
        ROOT / "vendor/brand/assets/Exo2-Bold.ttf", ROOT / "vendor/brand/lib-cover-font.mjs",
        ROOT / "vendor/brand/logo.svg", ROOT / "vendor/brand/node_modules/sharp/package.json",
    ]
    for name in ("fetch_google_serp.py", "build_article_serp_brief.py", "render_visuals.py",
                 "visual_renderer.mjs", "visual_verify.mjs", "workflow_gate.py", "gdoc_review.py",
                 "md_to_gdoc.py", "assemble_sections.py", "lint_article.py", "upload_visuals.py",
                 "package_article.py", "strapi_publish.py", "article_materials.py", "text_overlap.py"):
        required.append(BLOG / "scripts" / name)
    for path in required:
        if not path.exists():
            errors.append(f"Missing: {path.relative_to(ROOT)}")
    # Local credentials are git-ignored and never shipped: a fresh copy has none of them.
    for path, purpose in CREDENTIALS.items():
        if not (BLOG / "config" / path).exists():
            errors.append(f"Not configured: vendor/blog/config/{path} — {purpose}")
    try:
        from guide_api import load_profile
        execution = load_profile(ROOT / 'config/guide-execution.json')
        for stage, role in [('writer', 'guide-section-writer'), ('editor', 'guide-editor'), ('humanizer', 'guide-editor'), ('final_qa', 'guide-qa')]:
            route = routes.get(role, {})
            if (execution[stage]['model'], execution[stage]['reasoning_effort']) != (route.get('model'), route.get('reasoning_effort')):
                errors.append(f'API/native model-route registry mismatch: {stage}')
    except Exception as exc:
        errors.append(f'Invalid production API execution profile: {exc}')
    roles = sorted((ROOT / "agents-src/agents").glob("guide-*.md"))
    if len(roles) != 10:
        errors.append(f"Expected 10 roles, found {len(roles)}")
    for role in roles:
        profile = ROOT / ".codex/agents" / f"{role.stem}.toml"
        try:
            config = tomllib.loads(profile.read_text())
            if config.get("name") != role.stem:
                errors.append(f"Invalid role profile: {profile.name}")
            route = routes.get(role.stem, {})
            if not route.get("model") or route.get("reasoning_effort") != "medium":
                errors.append(f"Missing or invalid medium route: {role.stem}")
            if (config.get("model"), config.get("model_reasoning_effort")) != (
                    route.get("model"), route.get("reasoning_effort")):
                errors.append(f"Role profile differs from model route: {role.stem}")
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"Cannot read {profile.name}: {exc}")
    for module in ("google.oauth2.service_account", "googleapiclient.discovery", "markdown", "pytest"):
        try:
            found = importlib.util.find_spec(module)
        except ModuleNotFoundError:
            found = None
        if found is None:
            errors.append(f"Missing Python dependency: {module}")
    if shutil.which("node") is None:
        errors.append("Node.js is not on PATH")
    credential = BLOG / "config/google-service-account.json"
    if credential.exists():
        try:
            data = json.loads(credential.read_text())
            if data.get("type") != "service_account" or not data.get("private_key"):
                errors.append("Google credential is not a service-account key")
        except (OSError, ValueError):
            errors.append("Cannot parse Google credential")
    return errors


if __name__ == "__main__":
    issues = check()
    for issue in issues:
        print("BLOCK:", issue)
    if not issues:
        print("PASS: local paths, ten roles, Python dependencies and bundled Node assets.")
        print("Offline check only; API access and external permissions were not tested.")
    raise SystemExit(bool(issues))
