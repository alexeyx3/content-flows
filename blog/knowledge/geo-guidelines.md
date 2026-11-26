# GEO guidelines
Distilled from a third-party GEO agency's pre/post-publication checklist for content that AI answer engines select.
## Applicability
- **Every publication.** GEO tactics are platform-agnostic and carry no brand-lexicon constraint.
- Source is VENDOR MARKETING — figures are self-reported, treat as directional.


## Rules (verbatim-critical)
- **Author verified on an authority platform**: min. 3 publications under the author's name on an industry publishing platform or LinkedIn. Without it the AI cannot confirm the source's expertise (external author profile raises share-of-answer presence by ~18%).
- **Brand mentioned in independent sources**: media, industry catalogs, review aggregators. External-mention-to-citation correlation = 0.664 (Ahrefs Brand Radar). A brand with no external mentions does not exist as an authoritative entity to the AI.
- **Organization/Person schema with `sameAs` configured**: link the site to external-platform profiles to build a semantic identity graph. Matters for ChatGPT and Google AIO; for some regional search engines, heading structure matters more than markup.
- **Topic belongs to a site-wide topical cluster**: an isolated article is a weak signal. A cluster of 5+ interlinked materials makes the AI treat the site as a recognized niche expert (clusters significantly outperform scattered posts).
- **Run target prompts to map the competitive AI answer landscape**: 10-15 prompts reveal who dominates AI answers, in what format they're cited, which facts get used. Without it you build strategy blind.
- **Check real query frequency + semantics**: the AI cites what answers real user demand, not what the author thinks matters. Write to the questions the audience actually asks.
- **Define a unique angle / information novelty**: AI does not cite what it already knows. Provide an original fact, practical case, own research, or unexpected conclusion — if your info exists nowhere else, citation chance is maximal.
- **H1 contains the main thesis or the answer to a question**: 68.7% of cited pages follow H1->H2->H3 structure (ConvertMate / BrightEdge 2026). H1 must answer, not just name the topic.
- **H2s create self-contained semantic blocks**: each block answers one concrete question autonomously, independent of neighboring sections. Chaotic structure = broken context = lost citations.
- **FAQ block with real audience questions**: question-answer markup raises Google AI-answer inclusion 2.8x. Questions must exactly match real client queries.
- **Main thesis in the first paragraph, not in the conclusion**: pattern "Thesis -> Evidence -> Example" performs best. Avoid "since ancient times people sought..." style intros — a direct path to zero AI visibility.
- **Key statistic with a source within the first 200 words**: +41% AI visibility from stats with attribution (Princeton / KDD 2024). Not "research shows" but "per study X, figure Y" — a factual-reliability signal for the algorithm.
- **Key concept defined explicitly and concretely**: AIs extract clean definitions for "what is X" queries. An explicit definition early = "zero-answer" position (explicit definitions correlate with +12% presence).
- **15+ interrelated entities in the text**: entities = concrete mentions (people, organizations, tools, concepts) with relations between them; relations matter more than count. Pages with 15+ interrelated entities hit AI answers 4.8x more often — this is contextual richness, not keywords.
- **Full semantic cluster of the topic covered**: cover all adjacent concepts, not just core queries. Surface-level rewrite loses to expert analysis — the AI distinguishes them.
- **Contains an original fact found in no other source**: own research, client case, a measurement, an A/B test, an analytics screenshot — any unique data point. AI does not cite compilations.
- **Author's personal experience — concrete, with figures and dates**: not "we help clients grow" but "in March 2026 we audited 47 sites and found...". Specificity verifies expertise and makes text non-reproducible from the AI's own data.
- **Counterintuitive conclusion or paradoxical fact**: AI uses unexpected facts to enrich answers; such theses are extracted far more often than banal statements.
- **Authoritative sources attributed explicitly**: format "(data X, Q1 2026)". Attribution is a verifiability signal the algorithm scores directly. +41% visibility from adding concrete links.
- **Author identified and linked to external profiles**: a real person with a bio and links to industry publishing platforms and LinkedIn. The algorithm builds an "author picture" from publication history — consistent niche expertise raises trust in every new piece.
- **Creation and last-updated dates shown**: 50% of cited content is younger than 13 weeks. For Perplexity, updating within the last 30 days roughly doubles inclusion odds. Update date is a competitive advantage, not a formality.
- **Depth: 2900+ words for competitive topics**: 2900+ word content is cited far more than short pages (avg ~5.1 vs 3.2 citations; Virayo / Growth Memo 2026). Set optimal length by analyzing the top.
- **Pass a machine-generation check**: ensure personal examples, direct assertions (no "maybe/probably" hedging), varied sentence length, a subjective author stance. If everything reads "uniformly smooth" it's a red flag. (VERMILLION-type detectors flag 10 signals: monotone sentence length, mechanical transitions like "thus"/"moreover", no personal experience, avoidance of direct statements — 7+ of 10 = trust-signal downgrade.)
- **Exclude promo tone and marketing cliches**: "best solution on the market", "innovative approach" correlate with citability at -26% (Semrush 2025). AI prefers factual language; cliches signal an unreliable source.
- **robots.txt allows AI crawlers**: GPTBot, ChatGPT-User, ClaudeBot, PerplexityBot, anthropic-ai, Googlebot-Extended. Every unregistered bot = a lost presence channel. (`User-agent: GPTBot` / `Allow: /`). NOTE: Cloudflare blocks AI bots by default — site is invisible to them regardless of content quality; verify this first.
- **llms.txt added to site root**: 2025 standard — a file briefly describing the site's specialization so AIs grasp the resource's context without full crawling. Early adopters gain a lead.
- **Load speed in the green — Core Web Vitals**: LCP under 2.5s, CLS under 0.1. Some search engines pre-cache AI answers; slow pages don't make it and drop out of the source pool.
- **Question-answer markup added to the FAQ block**: structured FAQ enters Google AI answers 2.8x more than unmarked pages. For some regional search engines, heading structure beats markup — tune per platform; one approach does not fit all.
- **Original images — not stock, not AI-generated**: computer-vision algorithms detect image origin from artifacts, lighting, metadata. An original screenshot is verified proof of experience that raises trust.
- **Alt tags describe content — especially for data and charts**: AIs use image descriptions to pull visual info into context. An analytics screenshot without alt = lost context; with a correct description = an extra verified data source.
- **Publish or announce on industry publishing platforms**: authority domains with a direct signal to AIs. Content from large community platforms feeds ChatGPT training data — publishing there builds long-term presence in the model.
- **Social-network post linking to the material**: some search engines and assistants weigh user signals from social networks when forming AI answers; post where your audience is. This channel is critically under-used.
- **Expert answer on a professional forum**: 24% of Perplexity citations come from forums and Q&A sites. A concrete expert answer with a link (professional and niche communities) — not an ad.
- **YouTube video with a text transcript of the topic**: 23% of Google citations come from YouTube; transcripts are indexed as a separate document independent of the site. Even a short clip with the article's key theses adds a presence point.
- **Presence monitoring configured**: track 100+ prompts on the topic across 3+ platforms (for example Google AI Overviews, ChatGPT, Perplexity) monthly. Presence % = (mentions / prompts) x 100. Without a baseline metric you can't tell if the strategy works.
- **Stats refresh cycle: every 60-90 days**: find stale data, replace with current numbers + new source, update the on-page date. Not a rewrite — just refresh. One of the highest-ROI GEO actions.
- **Presence volatility tracked monthly**: 40-60% monthly volatility is normal; three consecutive months of decline = alarm, the article needs updating. Without monitoring, companies notice lost positions only after sales drop.

## Notes / context
- Source is a GEO agency's 37-point pre/post-publication GEO checklist from 2025-2026; the agency sells its own presence-measurement tool. Cited data sources: Ahrefs, Semrush, Growth Memo, Amsive, ConvertMate/BrightEdge, Princeton/KDD, Virayo.
- Five sections + their relative weight: 01 Presence foundation (7 pts, CRITICAL — without it AI doesn't know whom to trust); 02 Content structure (8 pts, HIGH — drives extraction ease); 03 Content & expertise (9 pts, HIGH — novelty + author trust); 04 Technical requirements (6 pts, BLOCKING — errors here zero out everything else); 05 Distribution & monitoring (7 pts, OPERATIONAL — sustains and scales results). Total 37.
- Scoring tiers: 30-37 (80%+) = ~3.2x higher citation odds; 22-29 (60-79%) = competitive but with open gaps; under 22 (<60%) = high risk, sections 01 and 02 are immediate priority. Goal stated by source: 80%+.
- Headline mechanic: "44% of AI citations are pulled from the first 30% of the text" — AI reads like a journalist, grabbing the opening; put thesis + key figure + source in the first two paragraphs, never in the conclusion.
- Quotable-stat template the source uses for every opening paragraph: "Thesis — Data — Source" (claimed to raise AI-answer inclusion +35%).
- Ecosystem mechanic "1 material = 6 points": one primary piece systematically distributed across channels (industry publishing platforms, a social network, forums, YouTube transcript, etc.) multiplies AI presence without proportional budget growth. AI seeks consensus: if only your site says it, that's an opinion; if several independent platforms confirm it, that's authority.
- Entities/topical-richness, freshness (<13 weeks for ~50% of cited content; <30 days strongly favored by Perplexity), explicit attribution, and clean self-contained passages recur as the strongest levers across multiple points.

## Empirical caveat
- Treat Google's official guidance as ONE input, NOT truth. Where a recommendation rests only on Google's official statements, mark it "declaration, verify in practice". Prioritize observed citation/ranking evidence over what Google says.
- Note the two GEO realities: Google AI Overviews tracks classic ranking closely (rank in top-20 matters); Perplexity/ChatGPT depend more on off-site presence + clean standalone passages than on your domain authority.
- Additional caveat specific to THIS source: it is vendor marketing for the agency's own measurement tool, and most quantitative claims (0.664 correlation, +41%, 4.8x, 3.2x, 2.8x, -26%, the 13-week/30-day freshness numbers) are self-reported or loosely attributed — treat all figures as directional, not verified. Check its advice against the search engines and assistants your audience actually uses, including regional ones where they matter; relevance to a given stack varies.
