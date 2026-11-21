---
name: deep-research
description: >
  Conduct extensive, multi-source research on complex topics using parallel web
  scouts, source authority tiers, iterative gap analysis, and a publication-grade
  report with verified citations. Requires web access via donsetch MCP tools.
  Triggers: deep research, multi-source research, publication-grade report,
  source tier audit, morning market research, competitive teardown.
---

# Autonomous Deep Research Skill (OpenCode-native)

This skill decomposes complex topics into orthogonal inquiry vectors, deploys
parallel web scouts to gather evidence, classifies sources into four authority
tiers, performs gap analysis to resolve contradictions, synthesizes a
publication-grade report with strict inline [N] citations, and runs an independent
critic validation loop before saving the final report.

Ported from the Antigravity `deep-research` skill: the deterministic engine
(`adaptive_vectors`, `eval_sources`, `read_page`, `gap_analysis`,
`source_classifier`) now matches the AGY implementation, while the orchestration
runs through OpenCode subagents and donsetch.

## End-to-End Architecture

```
Topic & Scope
    |
[Phase 0: Dynamic Scoping]  -> Lead Planner: 6-8 orthogonal inquiry vectors
    |
[Phase 1: Scout Wave 1]     -> 4x parallel web scouts: web_search + web_fetch
    |
[Phase 1.5: Source Filter]  -> Authority validator: dedupe, tier 1-4 classification
    |
[Phase 2: Gap Analysis]     -> Gap analyst: precision queries, Wave 2 scouts
    |
[Phase 3: Synthesis]        -> Lead synthesizer: 7-section report, [N] citations
    |
[Phase 4: Review]           -> Independent critic: citation verification, verdict
    |
Deliverables -> workspace/<topic-slug>-deep-research.md + conversation summary
```

## Instructions

### Step 1: Onboarding (optional scope clarification)

If the topic, scope, or depth is unclear, ask exactly one short question. Otherwise proceed.

Depth tiers:
- `standard` (default): Wave 1 scouts only
- `deep`: Wave 1 + Wave 2 gap analysis and precision queries

### Step 2: Phase 0 — Dynamic Scoping & Vector Decomposition

The Lead Planner dynamically generates 6–8 orthogonal inquiry vectors for the subject matter. Each vector must include:

- 2–4 targeted search queries with exact entity names and operators (`site:`, `filetype:pdf`, exact phrases)
- Prioritized primary source types for that domain
- Domain tag (e.g. `technology`, `market_industry`, `biopharma`, `geopolitics`, `consumer_product`, `systems_architecture`)

No rigid template silos — vectors are synthesized for the specific topic.

Deterministic helper (use it to ground or sanity-check the plan, and as the offline
fallback when the planner cannot run):

```bash
cd ~/.config/opencode/skills/deep-research/scripts
python -c "import adaptive_vectors as av; d=av.detect_domain('<topic>','<scope>'); v=av.generate_fallback_vectors('<topic>','<scope>',domain=d); print(d, av.validate_vectors(v))"
```

### Step 3: Phase 1 — Breadth Fan-out (Parallel Web Scouts)

Launch web-research subagents in parallel batches of 4 (adjust down if slots constrained). Each subagent:

1. Calls `tools.donsetch.web_search({query: <query>, max_pages: 10})` for its assigned queries.
2. For every result URL, calls `tools.donsetch.web_fetch({url: <url>})` to retrieve full page content.
3. Returns claims, source URLs, source quality notes, and uncertainty per vector.

Fallback: on `donsetch` error or empty results, retry once with builtin `webfetch` for individual URLs. Never mix unverified search results into evidence.

### Step 4: Phase 1.5 — Source Authority Filtering

The authority validator runs deterministic scripts:

- `scripts/source_classifier.py`: strips UTM/session params, deduplicates URLs, classifies each source into Tier 1–4.
- `scripts/eval_sources.py`: canonical URL resolution, redirect following, bare-root rejection, citation verification.
- Quota enforcement: ≥40% combined Tier 1 + Tier 2; Tier 3 within 5–15%; Tier 4 ≤40%.
- Discard 404s, blocked URLs, and bare root domains.
- Output: tier distribution report saved to `<topic>/tier_distribution.md`.

```bash
cd ~/.config/opencode/skills/deep-research/scripts
python source_classifier.py classify <url> [<url> ...]
python source_classifier.py quota <tier_counts_json>
```

### Step 5: Phase 2 — Gap Analysis (only when depth=deep)

The gap analyst ingests the evidence dossier and:

- Identifies quantitative deficits, contradictions, and generalizations.
- Generates 3–5 precision queries with advanced operators.
- Re-tasks web-research subagents (Wave 2) to resolve discrepancies.
- Tracks resolved vs unresolved issues for Section 5 of the final report.

`scripts/gap_analysis.py` renders the gap brief and the Section 5 skeleton from the
dossier; read its `build_gap_summary` output instead of retyping discrepancies.

### Step 6: Phase 3 — Grounded Draft Synthesis

The lead synthesizer writes `<topic-slug>-deep-research.md` in the current working directory with exactly 7 sections:

1. Executive Summary (with clickable `file:///` link to workspace report)
2. Key Findings (numbered findings with [N] citations and source links)
3. Detailed Analysis (narrative per vector with embedded tables)
4. Comparative Trade-off Matrix or Pareto Frontier
5. Contradictions, Disputed Claims & Strategic Risks (both sides, citations required)
6. Open Questions (what remains uncertain)
7. Bibliography (every source: title, author, date, URL, quality score, tier)

Strict grounding rules:
- Every factual assertion, number, benchmark, or historical claim MUST carry inline `[N]`.
- Every `[N]` must exist in the Section 7 bibliography.
- Bare root URLs are forbidden.
- No unresolved placeholders (`[Insert ...]`, `TODO`, `TBD`).
- Empirical precision over vague generalities.
- Embed primary HTML-extracted Markdown tables where tables exist on source pages (via `scripts/read_page.py`).

Report scaffold: `templates/report_template.md` holds the 7-section shell.

### Step 7: Phase 4 — Review & Validation Loop

The independent critic runs:

1. `scripts/eval_sources.py verify_citations()` — every `[N]` in draft matches bibliography entry.
2. `scripts/eval_sources.py ensure_report_bibliography()` — bibliography complete.
3. Manual cross-check: no placeholder text remains.

Verdicts: `WIN`, `WIN (WITH MINOR ADJUSTMENTS)`, or `NEEDS WORK`.
If `NEEDS WORK`, the orchestrator loops back to Phase 2 or Phase 3 for up to 3 iterations maximum.

### Step 8: Deliverables

1. Workspace report: `<topic-slug>-deep-research.md` saved in cwd.
2. Conversation artifact via `ctx_note`:
   ```json
   {
     "Summary": "Comprehensive Deep Research Report on <TOPIC>",
     "UserFacing": true,
     "RequestFeedback": false,
     "WorkspaceReport": "<topic-slug>-deep-research.md",
     "SourceCount": <N>,
     "TierDistribution": {"Tier1": N, "Tier2": N, "Tier3": N, "Tier4": N}
   }
   ```
3. Executive summary in conversation with clickable link: `[<topic-slug>-deep-research.md](file:///abs/path/to/report.md)`.
4. Research evidence metrics: total sources evaluated, tier distribution table.
5. Top 4–5 core empirical findings with numbers, latencies, or unit costs.

## Quality Gates

| Gate | Requirement |
|------|-------------|
| Source count | 30–100+ evaluated sources (deep), fewer for standard |
| Tier quota | ≥40% Tier 1 + Tier 2; Tier 3 5–15%; Tier 4 ≤40% |
| Citations | Every `[N]` matched to bibliography |
| Validation | Critic verdict must be WIN or WIN (WITH MINOR ADJUSTMENTS) |
| No bare roots | Every cited URL points to a specific page |

## Domain Authority Breakdown & Quota Matrix

The deep research pipeline enforces a rigorous 4-Tier Domain Authority and Source Category hierarchy:

| Tier | Source Category | Domain Archetypes & Registries | Target Quota | Verification Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Primary Official** (`primary_official`) | `.gov`, `.mil`, `.edu`, `.int`, WHO, UN, WTO, IMF, OECD, ISO, ASTM, ANSI, IEEE, ACM, NIST, USPTO, FDA, EMA, SEC EDGAR, PubMed, NCBI, ClinicalTrials.gov, arXiv, NEJM, Lancet, Nature, Science, Company Developer/Investor Docs (`docs.*`, `investor.*`) | **>= 25%** | Primary issuing authority, statutory regulatory body, verified peer-reviewed scientific literature, or original engineering specifications. Bare roots rejected. |
| **Tier 2** | **Investigative Testing** (`investigative_testing`) | Reuters, Bloomberg, WSJ, FT, Economist, NYT, BBC, AP, Nikkei Asia, Consumer Reports, Wirecutter, RTings, AnandTech, Tom's Hardware, iFixit, GSMArena, DPReview, StatNews, FiercePharma, TradeWinds, Aviation Week, Serious Eats, Ars Technica | **>= 20%** | Independent test lab methodology, verifiable instrumentation, teardown protocols, or credentialed financial/technical investigative journalism. |
| **Tier 3** | **Community Consensus** (`community_consensus`) | Reddit (`r/hardware`, `r/localllama`, `r/sysadmin`, `r/biotech`), GitHub Issues & Discussions, Stack Exchange / Stack Overflow, Hacker News, G2, Capterra, Trustpilot, Curated Practitioner Substack / Dev.to | **5% – 15%** | High-signal practitioner reports, real-world failure modes, unadvertised operational limits, and user defect clusters. |
| **Tier 4** | **General Web** (`general_web`) | General industry publications, corporate marketing blogs, verified news aggregators, product landing pages | **<= 40%** | Secondary references, contextual market commentary, and general background information. |

> **Quality Gate:** Deep research runs target at least **40%+ Tier 1 and Tier 2 sources** combined, guaranteeing that conclusions rest on verifiable empirical baselines and independent testing rather than marketing fluff.

## Strict Grounding Contract

> **Core Grounding Directives:**
> 1. **Mandatory Inline Anchors:** Every factual assertion, quantitative metric, benchmark comparison, historical claim, and pricing figure MUST carry an inline citation anchor `[N]` referencing the Section 7 bibliography.
> 2. **Zero Hallucinated URLs or Anchors:** Every cited index `[N]` must exist in the reference bibliography. Bare root domains (`https://example.com/`) are strictly filtered out during indexing.
> 3. **Zero Unresolved Placeholders:** Drafts containing placeholders (`[Insert ...]`, `[N]`, `TODO`, `TBD`) are rejected during Phase 4 validation.
> 4. **Empirical Precision Over Generalities:** Always prefer concrete measurements ("14.8% yield loss at 42-week substrate lead times", "$0.0015 per 1k tokens at p99 latency of 42ms") over vague claims ("significantly higher yield", "cost-effective").
> 5. **Document Discrepancies in Section 5:** When Tier 1 claims conflict with Tier 2 independent benchmarks or Tier 3 community feedback, never discard the divergence. Explicitly document both sides in Section 5 (*Contradictions, Disputed Claims & Strategic Risks*).

## Worked Scope Briefs

Use these as scope templates. Pass the four fields into Steps 2–3; they are the same
arguments the AGY orchestrator consumed, so a brief can be handed to
`scripts/deep_research_workflow.py` unchanged when a top-level-await agent runner
is available.

### 1. Consumer Product Comparison (Display Technology)
- **Topic:** OLED vs QD-OLED vs Mini-LED High-End 4K Displays (2024–2025)
- **Scope:** Panel physics, sustained peak brightness (10% window), ABL aggression, color volume (Rec.2020), pixel response times, burn-in risk curves from accelerated stress testing, and real-world value across gaming and productivity.
- **Hints:** Compare LG Display WOLED (META 2.0 / MLA) against Samsung Display QD-OLED (Gen 3) and top-tier Mini-LED backlights (TCL/Hisense 5,000+ dimming zones). Prioritize RTings 10-month burn-in test results, TFTCentral measurements, and DisplayHDR 1400 certifications.
- **Depth:** deep · **Domain:** consumer_product

### 2. Biopharma & Health Review (Metabolic Medicine)
- **Topic:** GLP-1 and Dual/Triple Receptor Agonists for Metabolic Dysfunction-Associated Steatohepatitis (MASH / NASH)
- **Scope:** Clinical trial efficacy (Phase 2b/Phase 3 ESSENCE, SYNERGY-NASH), histologic fibrosis stage improvement without worsening steatohepatitis, reduction in hepatic fat fraction by MRI-PDFF, gastrointestinal tolerability profile, and FDA accelerated approval timelines.
- **Hints:** Investigate semaglutide, tirzepatide, and retatrutide compared to resmetirom (Rezdiffra). Audit PubMed/NEJM primary publications, ClinicalTrials.gov endpoints, AASLD guidelines, and patient adherence rates.
- **Depth:** deep · **Domain:** biopharma_medicine

### 3. Market & Industry Analysis (Semiconductor Advanced Packaging)
- **Topic:** Global HBM3e and HBM4 Advanced Packaging Capacity & Supply Chain Chokepoints (2024–2026)
- **Scope:** Wafer-on-Wafer (WoW) and Chip-on-Wafer-on-Substrate (CoWoS) packaging bottlenecks, thermo-compression bonding (TCB) vs Advanced Reflow Molded Underfill (MR-MUF) yields, Ajinomoto Build-up Film (ABF) substrate availability, TSV defect densities, and capital allocation by SK Hynix, Samsung, and Micron.
- **Hints:** Analyze TSMC CoWoS allocation quotas for NVIDIA Blackwell and AMD MI300X, Yole Intelligence market share reports, SEC 10-K filings, and SIA packaging roadmaps.
- **Depth:** deep · **Domain:** market_industry_analysis

### 4. Geopolitical Supply Chain (Critical Minerals & Refining)
- **Topic:** Global Heavy Rare Earth Element (Dy/Tb) Separation & Permanent Magnet (NdFeB) Supply Chains
- **Scope:** Geopolitical concentration of ionic clay mining and solvent extraction separation, export control mechanisms under MOFCOM regulations, Western alternative refining scale-up (MP Materials, Lynas, Iluka), environmental permitting barriers, and defense supply chain exposure.
- **Hints:** Cite USGS Mineral Commodity Summaries, CSIS strategic reports, IEA Critical Minerals Market Review, US Department of Defense Title III Defense Production Act awards, and EU Critical Raw Materials Act targets.
- **Depth:** deep · **Domain:** geopolitics_macro

### 5. Technology Architecture (Local-First Synchronization)
- **Topic:** Local-First Software Architecture: CRDTs vs Operational Transformation (OT) in Production
- **Scope:** Memory footprint benchmarks, p99 sync latency over unreliable networks, tombstones and garbage collection overhead, state-based vs operation-based convergence proofs, and developer DX across Yjs, Automerge, ElectricSQL, and Replicache.
- **Hints:** Focus on Martin Kleppmann's papers, Figma's engineering blog on multi-player infrastructure, benchmark repositories measuring ops/sec on 100k+ edit traces, and real-world SQLite WASM syncing.
- **Depth:** deep · **Domain:** technology_software

## Engine Modules

| Module | Role | Entry point |
|---|---|---|
| `scripts/adaptive_vectors.py` | Domain detection, 6–8 fallback vectors, validation | library; `python adaptive_vectors.py` runs the self-demo |
| `scripts/eval_sources.py` | URL canonicalisation, redirect resolution, tier classification, citation verification, bibliography injection | library |
| `scripts/read_page.py` | Direct HTTP fetch with gzip/deflate, title extraction, DOM table → Markdown | library |
| `scripts/gap_analysis.py` | Gap brief rendering, Section 5 skeleton, discrepancy ledger | library |
| `scripts/source_classifier.py` | Deterministic tier/quota CLI | `python source_classifier.py classify\|quota` |
| `scripts/deep_research_workflow.py` | Full 7-phase orchestrator | needs a top-level-await runner that injects `agent`, `parallel`, `WORKSPACES`, `CONVERSATION_ID`; without one, run the phases through subagents as in Steps 2–7 |

Scratch artifacts (when `CONVERSATION_ID` is set) are written under
`${DEEP_RESEARCH_SCRATCH:-/tmp/opencode/deep-research}/brain/<CONVERSATION_ID>/`.

## Subagents Used

| Role | Type | Purpose |
|------|------|---------|
| lead_planner | general | Phase 0 vector decomposition |
| web_researcher | cavecrew-investigator | Parallel Wave 1 / Wave 2 web searches and fetches |
| authority_validator | cavecrew-investigator | Source classification, tier quota, dedupe |
| gap_analyst | general | Phase 2 precision queries, discrepancy tracking |
| lead_synthesizer | general | Phase 3 report writing with citations |
| critic | cavecrew-reviewer | Phase 4 citation verification, final verdict |

## Files Created by this Skill

- `~/.config/opencode/skills/deep-research/SKILL.md`
- `~/.config/opencode/skills/deep-research/README.md`
- `~/.config/opencode/skills/deep-research/scripts/deep_research_workflow.py`
- `~/.config/opencode/skills/deep-research/scripts/adaptive_vectors.py`
- `~/.config/opencode/skills/deep-research/scripts/eval_sources.py`
- `~/.config/opencode/skills/deep-research/scripts/gap_analysis.py`
- `~/.config/opencode/skills/deep-research/scripts/read_page.py`
- `~/.config/opencode/skills/deep-research/scripts/source_classifier.py`
- `~/.config/opencode/skills/deep-research/templates/report_template.md`
- `~/.config/opencode/skills/deep-research/tests/`
