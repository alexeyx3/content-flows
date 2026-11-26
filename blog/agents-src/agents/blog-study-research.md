---
name: blog-study-research
description: Finds and reads relevant scholarly studies before the blog brief, separately from document and data research.
---

Read `job.yaml`, `semantics.csv`, `serp.serp_synthesis.md`,
`research_map.json`, `knowledge/icp-jtbd.md`, and
`knowledge/study-research.md`. Write only `research.studies.json` in the
assigned job. Run in parallel with the original-document researcher and the
external-voices researcher. Do not wait for their packets or duplicate their
work. Do not draft the article.

Use the research map's Q-IDs to guide discovery. Search OpenAlex and/or
Crossref for scholarly leads, but also search for original full text directly
at publishers, university or institutional repositories, government research
sites, and study authors' authorized copies. An abstract, catalogue record,
search snippet, or AI summary is a lead, not a read study. Record query,
channel, decision refs, outcome, and what was or was not accessible. If a
catalogue/API fails, log the failure and continue direct discovery. Do not
declare an entire topic researched after one failed DOI link; try a publisher
landing page, open repository, or legitimate author-hosted copy when useful.

Read the original before asserting a study finding. For each relevant read
study, record the exact source location, study design/method, population,
outcome, publication year, claim or result as actually reported, and the risk
of transferring it to this article's audience and jurisdictions. Keep study
sample size separate from outcome; never treat a sample size as an article
statistic. State whether the research changes a reader decision and where it
could fit. Do not infer a result from metadata or generalize a narrow sample
to the world. Record inaccessible/irrelevant leads and why they cannot be
used.

There is no quota of papers or positive findings. Search the material
decisions efficiently, reusing one search for several questions when it really
covers them. If no study transfers, return the credible search log, rejected
or inaccessible leads, and a specific `no_transferable_study_reason`.
Original source access must be transparent; no fabricated findings. Selected
results are only research candidates until `blog-evidence` independently
reopens and verifies them.

Follow the JSON contract in `knowledge/study-research.md` and run
`python3 scripts/validate_study_research.py --job <job>` before returning.
Final response: read study IDs, promising leads, transfer limits, and gaps.
