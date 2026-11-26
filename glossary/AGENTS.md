# Glossary pipeline

- Use `.agents/skills/glossary-term/SKILL.md` for glossary term work in this project.
- Statements about the company's own product follow `knowledge/positioning.md`. That card is the single source of product rules for this flow; when the company's editorial policy changes, update the card.
- Brands listed in `config/stop-brands.json` are never mentioned anywhere: text, tables, sources, links, metadata, or images. The CMS script refuses a payload that contains one.
- The blog flow in `../blog` is a separate workflow. This flow reuses its visual renderer, Google Docs exporter, author mapping and writer-style card; do not change them from here.
- English is required for the glossary term, its outline, brief, metadata, evidence packet, draft, and Google Doc.
- Orchestrate flat depth-1 Codex specialists from `agents-src/agents/`; use `fork_turns="none"` and job-specific names. For new terms use the writer in `request.json`. The default is MiniMax via OpenRouter. Jobs without that field use the established Codex writer. Each writer keeps one continuous context per term and handles a full H2 without H3s, or one H3 with its H4 subtree per turn. Evidence, editing, and QA remain separate Codex roles.
- Keep every term's files under its own `jobs/<date>-<slug>/`. Record material workflow changes in `docs/design-notes.md` with the reason.
- Do not write to the CMS or publish without an explicit request for that action. Google Docs review uses the folder configured in `config/google-drive.json`; preserve its existing shared-drive permissions.
- Do not copy article prose or legal claims from other sites or from older pages. Verify unstable claims from current primary sources.
- After changing scripts, run their targeted checks. After changing the skill or the role files, run the flow's offline tests (`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests`) and check that every command, file and field the skill names still exists in `scripts/` and `docs/enrichment-contract.md`.
