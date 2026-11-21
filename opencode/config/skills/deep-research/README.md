# deep-research skill

OpenCode-native autonomous deep research skill. Decomposes topics into
orthogonal inquiry vectors, runs parallel web scouts, classifies source authority
tiers, performs gap analysis, synthesizes a publication-grade report with strict
inline citations, and validates via an independent critic loop.

## Installation

Ensure donsetch MCP is available (`tools.donsetch.web_search`, `web_fetch`, `web_crawl`).
Place this directory at:
`/home/rahul/.config/opencode/skills/deep-research/`

OpenCode auto-discovers skills from this directory. No restart required.

## Usage

Invoke the skill with a research topic:

```
/deep-research <topic>
```

Optional parameters:
- `scope`: target scope and objectives (default: open research)
- `hints`: user scoping hints for the lead planner
- `depth`: "standard" (Wave 1 only) or "deep" (default: deep)
- `domain`: optional domain override (e.g. `technology`, `market_industry`, `biopharma`, `geopolitics`, `consumer_product`, `systems_architecture`)

Example:

```
/deep-research compare OLED vs QD-OLED vs Mini-LED 4K displays 2024-2025
  depth=deep domain=consumer_product
```

Or via `run_workflow`:

```python
run_workflow(
    ScriptPath="/home/rahul/.config/opencode/skills/deep-research/scripts/deep_research_workflow.py",
    Description="Deep research on OLED vs QD-OLED vs Mini-LED",
    Args={
        "topic": "OLED vs QD-OLED vs Mini-LED High-End 4K Displays (2024-2025)",
        "scope": "Comprehensive evaluation of panel physics, brightness, ABL aggression, color volume, response times, burn-in risk, value.",
        "depth": "deep",
        "domain": "consumer_product"
    }
)
```

## Onboarding Interview

If topic or depth is unclear, the skill asks exactly one short question:

> "How long do you want this research task to run?"

- A few minutes → standard depth
- ~10-15 minutes → deep depth
- Longer / no limit → deep depth with extended Wave 2

If the topic itself is unclear, at most 1-2 additional concise questions.

## Output

The skill saves `<topic-slug>-deep-research.md` in the current working directory
and delivers an executive summary in the conversation with a clickable
`file:///` link.

## Requirements

- OpenCode with skills enabled
- donsetch MCP tools configured (`web_search`, `web_fetch`)
- No third-party API keys required (uses free web access via donsetch)

## Scripts

- `deep_research_workflow.py` — orchestrates Phase 0 through Phase 4
- `eval_sources.py` — citation verification, bibliography enforcement
- `read_page.py` — HTML fetching, decompression, DOM table extraction
- `source_classifier.py` — URL normalization, tier classification, dedupe, quota gating

## Quality Gates

- 6–8 orthogonal inquiry vectors
- 30–100+ evaluated sources (deep mode)
- ≥40% Tier 1 + Tier 2 sources
- Every `[N]` citation matched to bibliography
- Critic verdict: WIN or WIN (WITH MINOR ADJUSTMENTS)
