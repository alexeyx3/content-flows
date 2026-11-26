---
name: copywriter
description: Write, edit, or audit public-facing Example Co text for country guides using this project's current positioning (the product rules), legal rules, and editorial voice. Use for Example Co copy inside the country-guide workflow.
---

# Example Co copywriter

This skill supplies voice and compliance judgment. It does not replace the guide pipeline or its evidence gate. It is deliberately short: the rules live in the knowledge files below. Do not rebuild long vocabulary tables here; a second copy of the rules goes stale the first time the product card changes.

## Source priority

Read the relevant current files before writing:

1. `knowledge/guides-rules.md` — binding rules for every guide page; section 2 covers how Example Co is described, section 6 the ranking.
2. `knowledge/product-positioning.md` — «Naming & category» and §1 (the product rules): category formula, client-side description, approval wording, who uses the product, coverage, price, and everything forbidden next to Example Co.
3. `references/checklist.md` — the short pre-handoff check.
4. `vendor/blog/knowledge/legal.md` — comparative and substantiation rules.

A later rule from the publisher overrides earlier material. The source of truth for the rules is `knowledge/product-positioning.md`; when it changes, `knowledge/guides-rules.md` sections 2 and 6, `references/checklist.md` and `scripts/check_guide.py` change with it.

## Non-negotiable writing behavior

- Use `Example Co` exactly as the brand name; the product is Example Workspace.
- Describe Example Co from the client's side: companies keep contractor agreements and approve contractor invoices in Example Workspace.
- Name invoice approval where Example Co is described, not in every sentence, and vary the wording (invoice approval / approvals / sign-off).
- Never present Example Co as the party that pays, employs, sources or advises: the company pays through its own bank or payment service.
- Never invent product capabilities, certifications, liability coverage, geography, prices, customer counts, or legal conclusions.
- Make comparative claims only when evidence supports the exact scope and wording; give competitors genuine strengths and limitations without disparagement.
- Keep internal plans, roadmap dates, unpublished names, and sales arguments out of public copy.
- Prefer concrete operational consequences over slogans and superlatives. No conversational or hedged tone in sentences about Example Co.

## Output

For writing requests, return the requested copy. For audits, identify blocking violations first, cite the governing file, and offer corrected wording.
