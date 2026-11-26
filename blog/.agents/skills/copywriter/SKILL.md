---
name: copywriter
description: Write, edit, or audit public-facing Example Co text using the repository's current positioning, owned-channel restrictions, legal rules, and editorial voice. Use for Example Co copy; for full blog production also use the blog-article skill.
---

# Example Co copywriter

This skill supplies voice and compliance judgment. It does not replace the article pipeline or its evidence gate.

## Source priority

For work in this repository, read the relevant current files before writing:

1. `knowledge/blog-owned.md` for blog-specific binding rules and banned framing.
2. `knowledge/positioning.md` for the current product and category truth.
3. `knowledge/editorial-owned.md` and `knowledge/article-structure-rules.md` for editorial form.
4. `knowledge/legal.md` for comparative and substantiation rules.
5. `knowledge/icp-jtbd.md` for audience and jobs-to-be-done.

Later dated decisions override earlier material. Job-specific `job.yaml`, `brief.md`, and verified `evidence.md` narrow the task but cannot relax legal or factual constraints. Do not use archived jobs or the old files under this skill's `references/` as a product source of truth.

## Non-negotiable writing behavior

- Use `Example Co` exactly as the brand name.
- Describe the current product using the public terminology permitted by `knowledge/positioning.md`; do not turn internal category shorthand or roadmap names into public product names.
- Never invent product capabilities, certifications, liability coverage, geography, prices, customer counts, or legal conclusions.
- Make comparative claims only when `evidence.md` supports the exact scope and wording.
- Give competitors genuine strengths and relevant limitations without disparagement.
- Follow the product rules exactly as defined in `knowledge/positioning.md` («Naming & category», §1) and `knowledge/blog-owned.md`: invoice approval belongs in the Example Co description; forbidden labels, speed claims, guarantees, unsourced superlatives, lists of regions and roadmap items stay out.
- Keep internal plans, roadmap dates, unpublished names, sales arguments, and negotiation material out of public copy.
- Prefer concrete operational consequences over slogans, inflated superlatives, and generic reassurance.
- Write in the requested language. Keep public copy natural; do not expose SEO instructions, research mechanics, prompt language, or source-access failures.

## Blog boundary

When producing a full article, `evidence.md` is the only source of publishable facts. This skill may improve expression and compliance but must not introduce a new factual claim from memory or from `companies/` directly.

Use the repo-local `humanizer` skill during the editing stage. The humanizer may change form, rhythm, and structure; it must preserve verified meaning and current positioning.

## Output

For writing requests, return the requested copy. For audits, identify blocking violations first, cite the governing repository file, and offer corrected wording. Do not add a long checklist when the user asked only for copy.

