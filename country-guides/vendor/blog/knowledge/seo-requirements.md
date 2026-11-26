# SEO requirements (general)
Source: distilled from the publisher's general article-requirements sheet.
## Applicability
- **Both tracks.** These are the general article-quality requirements; they apply to every
  publication regardless of voice.


## Rules (verbatim-critical)

- **First screen must answer immediately.** No long intros, market history, or general musings. First 1–2 paragraphs must contain: (a) main thesis/definition, (b) key takeaway that can be quoted without reading the full article, (c) a figure or fact with source (aim for it; not always possible). Formula: [Direct answer to the main question]. [Who this matters to]. [What criteria/topics the article will cover].

- **Thesis — data — source formula.** Every thesis, especially the first paragraph under each subheading, must be backed by proof and a link to that proof.

- **Each heading/subheading is a self-contained semantic block.** If you pull a subheading and its text out of the article in isolation, it must still make sense without the article's overall context.

- **Each section must open with an answer to the question posed by its heading.** (Follows from rules 1 and 3 — reinforced explicitly.)

- **Put the most important information in the first 30% of the text.** Answers can be formatted as paragraphs, tables, or lists — LLMs favor structured information.

- **Give explicit definitions for key terms.** If a term in the article could be queried by a user as "what is X", provide a short definition at the start or in the first relevant section. Definition requirements: short, specific, understandable outside the article's context.

- **Write through entities and their relationships.** GEO cares about density of topical entities: companies, tools, concepts, roles, scenarios, sources, etc. In SEO this overlaps with LSI / topically relevant vocabulary. This usually emerges naturally from thorough writing; do not treat it as a separate checklist item — just do not strip topical terms out.

- **Add informational novelty.** LLMs cite original data better than compilations of known facts; search engines also favor it. Enrich articles with fresh OR LLM-unknown data. Acceptable novelty types: own analysis ("we studied 20 top articles…"), mini-research, client insights from interviews, practical conclusions, original comparison tables with angles not used by competitors, counter-intuitive theses with evidence.

- **FAQ must be built from real audience questions, not author imagination.** Sources: Google search suggestions, People Also Ask, sales team questions, JTBD interview data, call transcripts, community chats, ChatGPT/Perplexity prompts, questions from competing top-ranking articles. Good question patterns: "How much does X cost?", "What is the difference between X and Y?", "When should I choose X?", "What should I check before buying X?", "Can X replace Y?", "What are the limitations of X?" — not: "Why is our product amazing?", "Is our service convenient?"

- **Every article must have an author-expert.** (Editorial/publishing concern, not writing concern — but mandatory.)

- **Indicate update date both in the metadata block and inline in the text** ("data current as of [date]"). Note on content updates (from Google patent US20120209838A1): meaningful updates require at minimum one of — title update, addition of a new substantial section, changes to links (anchor text, donor page, or surrounding text). Changing only the date or rearranging a few words is ignored by Google. JavaScript, ads, navigation, and template blocks are also ignored.

- **Depth calibrated by competitors, not by a fixed word count.** Take the highest-frequency query, search Google, check the size of top-10 articles, then write an article that answers the query more fully and better than any competitor. "Fuller and better" usually means longer, but not always. Bad: 5000 words of obvious facts and padding. Good: 3000–4000 words with tables, examples, FAQ, sources, and editorial conclusions.

- **Remove promotional tone and marketing clichés.** Standalone marketing blocks within the article are acceptable, but the primary goal is usefulness. Prohibited phrases (non-exhaustive): "best solution", "innovative approach", "unique platform", "revolutionary service", "guaranteed result", "without risks", "perfect for everyone", "most advantageous", "#1 on the market". Acceptable alternatives: "suitable for companies that care about…", "may be useful if…", "worth considering in the scenario of…", "focuses on…", "helps reduce manual work via…", "may not be suitable if…".

- **The article must not read as unedited AI output.** Target: AI-detection score no higher than 30% AI-generated. Fix markers: monotone sentence length → alternate short and long; mechanical transitions ("thus", "moreover") → remove; no specifics → add numbers, dates, examples, cases; no author position → add editor/expert conclusions; excessive hedging ("may", "probably", "possibly") → reduce; text too smooth → add real observations, limitations, practical tips. Neutral tone must not become faceless text.

- **Use original images and graphics, not stock art.** Preferred: custom diagrams, product screenshots, tables, data-driven charts, process diagrams, author checklists. Do not use stock images or abstract AI-generated art just to fill space. If an image illustrates nothing, it is not needed.

- **Key data must not be locked inside images.** If there is a table, chart, or diagram — duplicate the key conclusions in text. Tables must be HTML markup, not images. Rule: everything important for understanding the article must be accessible as HTML text. An image may reinforce the material but must not be the sole carrier of meaning.

- **Cover a topic with a cluster, not a single article.** Plan clusters: e.g., "Best X alternatives" → supporting pages: "X vs Y", "how to choose X", "pricing guide", "checklist", "FAQ", "implementation guide". Inside the main article, place internal links to supporting materials (where they exist).

- **Write each article so that individual blocks — definitions, tables, conclusions, FAQs, checklists — can be extracted and reused** as social posts, expert answers (Quora-type), LinkedIn/VC/Habr versions, YouTube scripts, PDFs.

- **For Example Co articles: editorial policy and positioning documents take precedence over these requirements.** These SEO/GEO rules are additive, not overriding.

## Notes / context

- The TL;DR from the source: the article must not be an SEO text for keywords' sake, but a full expert material that completely closes the user's query and delivers more value than any competitor in the top results.

- GEO-specific: each important block should start with a short self-contained answer; H2/H3 should be clear semantic sections; the article should contain definitions, tables, FAQ, update dates, sources, and original conclusions or data — so LLMs can cite it easily.

- Rule 11 (author/expert attribution) and Rule 19 (post-publication updates) and Rule 20 (multi-format reuse) are publishing/editorial concerns, not article-writing concerns — flagged as such in the source.

- The "2900 words" figure mentioned in the source under Rule 13 is described as "an average across the board" and is explicitly replaced by the competitor-calibration method. It should not be used as a target.

- Google patent US20120209838A1 is cited as the basis for the content-update significance rules. This is a Google declaration; verify effects in practice.

## Empirical caveat

- Word count is a GUARDRAIL, not a target — drive by coverage (entities/subtopics/questions), not length.
- Treat Google's official guidance as one input, not truth; where a requirement rests only on Google's statements, mark "declaration, verify in practice".
