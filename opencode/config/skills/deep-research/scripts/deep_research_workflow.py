#!/usr/bin/env python3
"""
Deep Research Autonomous Workflow for OpenCode.
Modeled after Stanford STORM and Gemini Web Deep Research.
Orchestrates parallel scouts, source deduplication, gap analysis,
grounded synthesis, and critic validation.
"""

import ast
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure helper modules are importable
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import adaptive_vectors
import eval_sources
import gap_analysis
import read_page

# Fallback definitions for local/standalone test environments
if "log" not in globals():
    def log(*msg_args):
        print("[deep-research]", *msg_args)

if "phase" not in globals():
    def phase(name):
        print(f"\n=== [Phase] {name} ===")

if "WORKSPACES" not in globals():
    WORKSPACES = (os.getcwd(),)

if "args" not in globals():
    args = {}


async def run_batched_parallel(tasks, fn=None, batch_size=4):
    """
    Executes tasks in batches to respect rate limits and quota allocations.
    Accepts either (tasks, fn, batch_size) where fn(item) returns an awaitable agent,
    or (tasks, batch_size) where tasks is a list of awaitable agent calls.
    """
    if not tasks:
        return []

    if isinstance(fn, int):
        batch_size = fn
        fn = None

    results = []
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        try:
            if fn is not None:
                batch_res = await parallel(batch, fn)
            else:
                batch_res = await parallel(batch, lambda x: x)
            if isinstance(batch_res, (list, tuple)):
                results.extend(batch_res)
            elif batch_res is not None:
                results.append(batch_res)
        except Exception as e:
            log(f"Warning: Batch parallel execution encountered issue ({e}); proceeding with collected results.")
    return results


def extract_urls_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extracts markdown links [title](url) and raw http(s) URLs from arbitrary text.
    """
    if not text or not isinstance(text, str):
        return []

    found: List[Dict[str, str]] = []
    seen_urls: Set[str] = set()

    # 1. Extract markdown links
    md_pattern = r"\[([^\]]+)\]\((https?://[^\s\)]+)\)"
    for title, url in re.findall(md_pattern, text):
        clean = eval_sources.clean_url(url)
        if clean and clean not in seen_urls and eval_sources.is_valid_source_url(clean):
            seen_urls.add(clean)
            found.append({"url": clean, "title": title.strip()})

    # 2. Extract plain URLs
    raw_pattern = r"(?<!\()(https?://[^\s<>\"'\[\]\)]+)"
    for url in re.findall(raw_pattern, text):
        clean = eval_sources.clean_url(url)
        if clean and clean not in seen_urls and eval_sources.is_valid_source_url(clean):
            seen_urls.add(clean)
            found.append({"url": clean, "title": ""})

    return found


def generate_default_storm_vectors(
    topic: str,
    scope: str = "",
    domain: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generates 6-8 tailored orthogonal inquiry vectors using adaptive domain detection.
    Maintains compatibility with legacy callers while leveraging adaptive_vectors.
    """
    return adaptive_vectors.generate_fallback_vectors(topic, scope=scope, domain=domain)


SCOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "vector": {"type": "string"},
        "summary": {"type": "string"},
        "key_findings": {
            "type": "array",
            "items": {"type": "string"}
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    "snippet": {"type": "string"}
                },
                "required": ["url"]
            }
        }
    },
    "required": ["vector", "summary", "sources"]
}

GAP_ANALYST_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_critique": {"type": "string"},
        "identified_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap_type": {
                        "type": "string",
                        "enum": [
                            "quantitative_deficit",
                            "contradiction",
                            "unverified_claim",
                            "missing_subtopic",
                        ],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "conflicting_claims": {"type": "string"},
                    "targeted_query": {"type": "string"},
                    "search_operator_type": {
                        "type": "string",
                        "enum": [
                            "exact_quote",
                            "site_restricted",
                            "filetype_pdf",
                            "comparative_pair",
                            "keyword_precision",
                        ],
                    },
                    "focus_entities": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "gap_type",
                    "title",
                    "description",
                    "targeted_query",
                ],
            },
        },
    },
    "required": ["executive_critique", "identified_gaps"],
}

SYNTHESIZER_SCHEMA = {
    "type": "object",
    "properties": {
        "report_markdown": {"type": "string"},
        "summary": {"type": "string"}
    },
    "required": ["report_markdown"]
}

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "audit_notes": {"type": "string"},
        "corrected_report_markdown": {"type": "string"}
    },
    "required": ["approved", "corrected_report_markdown"]
}


async def main():
    topic = args.get("topic", "Emerging AI Architecture and Autonomous Systems")
    scope = args.get("scope", "Deep technical, economic, and operational evaluation")
    depth = args.get("depth", "standard")  # standard or deep
    user_hints = args.get("hints", "")
    domain_override = args.get("domain", None)
    custom_vectors = args.get("vectors", [])

    log(f"Starting Deep Research for topic: '{topic}' [Depth: {depth}]")

    # -------------------------------------------------------------
    # Phase 0: Dynamic Scoping & Adaptive Vector Planning
    # -------------------------------------------------------------
    phase("Phase 0: Dynamic Scoping & Adaptive Vector Planning")
    log("Deploying Lead Research Planner to semantically analyze domain and synthesize orthogonal inquiry vectors...")

    vectors: List[Dict[str, Any]] = []

    # 1. Respect explicit custom vectors if provided
    if custom_vectors and isinstance(custom_vectors, list) and len(custom_vectors) >= 3:
        log(f"Using {len(custom_vectors)} user-supplied custom inquiry vectors.")
        vectors = [
            {
                "id": f"v_{idx}",
                "name": v if isinstance(v, str) else v.get("name", f"Vector {idx}"),
                "focus": v if isinstance(v, str) else v.get("focus", f"{v} for {topic}"),
                "search_queries": [] if isinstance(v, str) else v.get("search_queries", []),
                "primary_source_types": [] if isinstance(v, str) else v.get("primary_source_types", []),
            }
            for idx, v in enumerate(custom_vectors, 1)
        ]
    else:
        # 2. Dynamic LLM-driven synthesis via Lead Research Planner (model="flash")
        planner_prompt = adaptive_vectors.build_planner_prompt(
            topic=topic,
            scope=scope,
            user_hints=user_hints,
        )

        try:
            planner_agent = agent(
                prompt=planner_prompt,
                schema=adaptive_vectors.PLANNER_SCHEMA,
                role="Lead Research Planner",
                type_name="self",
                model="flash",
            )
            planner_res = await planner_agent
            candidate_vectors = planner_res.get("vectors", []) if isinstance(planner_res, dict) else []
            is_valid, validation_errors = adaptive_vectors.validate_vectors(candidate_vectors)

            if is_valid:
                vectors = candidate_vectors
                domain_desc = planner_res.get("domain_analysis", "Dynamic Synthesis")
                log(f"Lead Planner synthesized {len(vectors)} dynamic inquiry vectors for domain: '{domain_desc}'")
                log(f"Scoping Rationale: {planner_res.get('scoping_rationale', '')}")
            else:
                log(f"Planner vectors did not pass strict validation ({validation_errors}); deploying resilient fallback planner.")
                vectors = adaptive_vectors.generate_fallback_vectors(topic, scope, domain=domain_override)
        except Exception as e:
            log(f"Lead Planner agent execution unavailable or failed ({e}); deploying resilient fallback planner.")
            vectors = adaptive_vectors.generate_fallback_vectors(topic, scope, domain=domain_override)

    # Ensure vectors is non-empty
    if not vectors:
        log("Notice: No vectors generated; utilizing resilient fallback inquiry vectors.")
        vectors = adaptive_vectors.generate_fallback_vectors(topic, scope, domain=domain_override)

    for v in vectors:
        log(f" - Vector [{v.get('id')}]: {v.get('name')}")

    # -------------------------------------------------------------
    # Phase 1: Scouting - Wave 1 (Breadth Fan-out)
    # -------------------------------------------------------------
    phase("Phase 1: Scouting - Wave 1 (Breadth Fan-out)")
    log(f"Deploying {len(vectors)} parallel scouts across domain-tailored inquiry vectors...")

    def build_scout_agent(vector_info):
        if not isinstance(vector_info, dict):
            vector_info = {"name": str(vector_info), "focus": str(vector_info)}
        vec_name = vector_info.get("name", "Inquiry Vector")
        vec_focus = vector_info.get("focus", topic)
        search_queries = vector_info.get("search_queries", [])
        source_types = vector_info.get("primary_source_types", [])

        queries_block = ""
        if search_queries:
            q_list = "\n".join(f"  - `{q}`" for q in search_queries)
            queries_block = f"Recommended Targeted Search Queries:\n{q_list}\n\n"

        sources_block = ""
        if source_types:
            s_list = ", ".join(source_types) if isinstance(source_types, list) else str(source_types)
            sources_block = f"Prioritized Primary Source Types: {s_list}\n\n"

        prompt = (
            f"You are a specialized Web Research Scout conducting an in-depth investigation on: '{topic}'.\n"
            f"Your Assigned Inquiry Vector: '{vec_name}'.\n"
            f"Specific Focus & Research Criteria:\n{vec_focus}\n\n"
            f"{queries_block}"
            f"{sources_block}"
            f"Instructions:\n"
            f"1. Perform multiple web searches using `search_web` starting with the recommended targeted queries, extracting primary documentation, peer-reviewed articles, benchmarks, and quantitative reports.\n"
            f"2. Gather hard empirical metrics, dates, specific names, cost figures, and exact citations.\n"
            f"3. Return a comprehensive summary, bulleted key findings with figures, and all unique source URLs with titles."
        )
        return agent(
            prompt=prompt,
            schema=SCOUT_SCHEMA,
            role=f"Scout: {vec_name[:24]}",
            type_name="self",
            model="flash_lite"
        )

    try:
        wave1_results = await run_batched_parallel(vectors, build_scout_agent, batch_size=4)
    except Exception as e:
        log(f"Warning: Wave 1 scouts encountered issue ({e}); proceeding with collected data.")
        wave1_results = []
    log(f"Wave 1 completed. Received {len(wave1_results)} scout dossiers.")

    # Ingest raw sources
    raw_sources: List[Dict[str, Any]] = []
    evidence_dossier: List[Dict[str, Any]] = []

    for res in (wave1_results or []):
        if not isinstance(res, dict):
            continue
        vec = res.get("vector", "General")
        summary = res.get("summary", "")
        key_findings = res.get("key_findings", [])
        if isinstance(key_findings, str):
            key_findings = [key_findings]
        elif not isinstance(key_findings, list):
            key_findings = []

        evidence_dossier.append({
            "vector": vec,
            "summary": summary,
            "key_findings": key_findings
        })

        # Sources from structured field
        sources_field = res.get("sources", [])
        if isinstance(sources_field, list):
            for s in sources_field:
                if isinstance(s, dict) and s.get("url"):
                    raw_sources.append(s)
                elif isinstance(s, str) and s.startswith("http"):
                    raw_sources.append({"url": s, "title": ""})

        # Sources parsed from text
        if summary:
            extracted_from_summary = extract_urls_from_text(summary)
            raw_sources.extend(extracted_from_summary)
        for kf in key_findings:
            if isinstance(kf, str):
                raw_sources.extend(extract_urls_from_text(kf))

    if not evidence_dossier:
        log("Notice: Empty evidence dossier from Wave 1; initializing baseline scoping entry.")
        evidence_dossier.append({
            "vector": "General Topic Scoping",
            "summary": f"Initial scoping investigation for topic: {topic}. Limited empirical sources retrieved in initial wave.",
            "key_findings": [f"Scoping initiated for {topic}."],
        })

    # -------------------------------------------------------------
    # Phase 1.5: Source Deduplication & Credibility Scoring
    # -------------------------------------------------------------
    phase("Phase 1.5: Source Deduplication & Credibility Scoring")
    try:
        citation_map = eval_sources.build_citation_map(raw_sources, resolve_redirects=True)
    except Exception as e:
        log(f"Warning: Citation map creation with redirects failed ({e}); falling back without redirect resolution.")
        citation_map = eval_sources.build_citation_map(raw_sources, resolve_redirects=False)

    dist = citation_map.get("credibility_distribution", {})
    log(f"Indexed {dist.get('total', 0)} unique canonical sources.")
    log(f"Authority Distribution -> Tier 1 (Primary Official): {dist.get('tier_1_count', 0)} ({dist.get('tier_1_pct', 0.0)}%) | "
        f"Tier 2 (Testing & Journalism): {dist.get('tier_2_count', 0)} ({dist.get('tier_2_pct', 0.0)}%) | "
        f"Tier 3 (Community Consensus): {dist.get('tier_3_count', 0)} ({dist.get('tier_3_pct', 0.0)}%) | "
        f"Tier 4 (General Web): {dist.get('tier_4_count', 0)} ({dist.get('tier_4_pct', 0.0)}%)")
    log(f"Community Consensus Signals: {dist.get('community_consensus_count', 0)} sources indexed.")

    # -------------------------------------------------------------
    # Phase 1.6: Deep Primary Source Inspection
    # -------------------------------------------------------------
    phase("Phase 1.6: Deep Primary Source Inspection")
    log("Selecting high-value primary sources (Tier 1 official docs, Tier 2 benchmarks, Tier 3 consensus) for deep page extraction...")

    citations_dict = citation_map.get("citations", {})
    # Identify top priority sources: Tier 1 official docs, Tier 2 benchmark labs, key Tier 3 consensus
    tier1_candidates = [
        (idx, c) for idx, c in citations_dict.items()
        if isinstance(c, dict) and c.get("tier") == 1
    ]
    tier2_candidates = [
        (idx, c) for idx, c in citations_dict.items()
        if isinstance(c, dict) and c.get("tier") == 2
    ]
    tier3_candidates = [
        (idx, c) for idx, c in citations_dict.items()
        if isinstance(c, dict) and c.get("tier") == 3
    ]

    # Select balanced representation: up to 4 Tier 1, up to 3 Tier 2, up to 2 Tier 3
    inspected_urls: Set[str] = set()
    deep_targets: List[Tuple[int, Dict[str, Any]]] = []

    for idx, c in (tier1_candidates[:4] + tier2_candidates[:3] + tier3_candidates[:2]):
        u = c.get("url")
        if u and u not in inspected_urls:
            inspected_urls.add(u)
            deep_targets.append((idx, c))

    log(f"Deep Primary Source Inspection: dispatched {len(deep_targets)} high-value targets for full extraction.")

    deep_extracted_count = 0
    total_tables_extracted = 0

    for idx, c in deep_targets:
        url = c.get("url", "")
        if not url:
            continue
        domain = c.get("domain", "")
        tier = c.get("tier", 1)
        cat = c.get("source_category", "primary_official")
        title = c.get("title") or domain

        try:
            page_summary = read_page.extract_page_content_summary(url, max_chars=12000, timeout=6.0)
        except Exception as e:
            log(f"Page extraction error for {url}: {e}")
            page_summary = {"success": False}

        if page_summary.get("success"):
            deep_extracted_count += 1
            tables = page_summary.get("tables", [])
            total_tables_extracted += len(tables)

            table_block = ""
            if tables:
                table_block = f"\n\n#### Extracted Primary Tables ({len(tables)}):\n" + "\n\n".join(tables)

            text_excerpt = (page_summary.get("text") or "")[:3500]
            page_title = page_summary.get("title") or title

            evidence_dossier.append({
                "vector": f"Deep Primary Page Evidence: [{idx}] {domain} - {page_title[:45]}",
                "summary": (
                    f"Direct Primary Source [{idx}]: {url} (Tier {tier} [{cat}])\n"
                    f"Document Title: {page_title}\n\n"
                    f"Verified Content Excerpt:\n{text_excerpt}"
                    f"{table_block}"
                ),
                "key_findings": [
                    f"Primary page verified and parsed directly from {url} [{idx}]",
                    f"Extracted {len(tables)} structured markdown data tables",
                ] + ([f"Tabular metrics preserved for cross-source comparison"] if tables else []),
            })

    log(f"Phase 1.6 complete: extracted {deep_extracted_count}/{len(deep_targets)} pages, ingested {total_tables_extracted} structured Markdown tables.")

    # -------------------------------------------------------------
    # Phase 2: Gap Analysis & Wave 2 Deep Dive
    # -------------------------------------------------------------
    phase("Phase 2: Gap Analysis & Wave 2 Deep Dive")
    log("Running Lead Gap Analyst to detect quantitative deficits, cross-source contradictions, and precision queries...")

    gap_prompt = gap_analysis.build_gap_analyst_prompt(
        topic=topic,
        evidence_dossier=evidence_dossier,
        citation_dist=dist,
    )

    try:
        lead_gap_analyst = agent(
            prompt=gap_prompt,
            schema=GAP_ANALYST_SCHEMA,
            role="Lead Gap Analyst",
            type_name="self",
            model="flash",
        )
        gap_result = await lead_gap_analyst
        if not isinstance(gap_result, dict):
            gap_result = {}
    except Exception as e:
        log(f"Warning: Lead Gap Analyst execution failed or timed out ({e}); deploying resilient fallback gap critique.")
        gap_result = {
            "executive_critique": f"Automated gap analysis fell back to heuristic critique: {e}",
            "identified_gaps": []
        }

    is_valid, validation_errors = gap_analysis.validate_gap_analysis(gap_result)
    if not is_valid:
        log(f"Warning: Gap analyst response had validation issues: {validation_errors}")

    critique = gap_result.get("executive_critique", "")
    log(f"Gap Analyst Executive Critique: {critique[:120]}...")

    identified_gaps = gap_result.get("identified_gaps", []) or []
    categorized = gap_analysis.categorize_gaps(identified_gaps)
    log(f"Identified {len(identified_gaps)} strategic gaps:")
    for g_type, g_list in categorized.items():
        if g_list:
            log(f" - [{g_type.upper()}]: {len(g_list)} gap(s)")
            for g in g_list:
                log(f"    * {g.get('title')}: `{g.get('targeted_query')}` [{g.get('search_operator_type', 'keyword_precision')}]")

    precision_items = gap_analysis.extract_precision_queries(gap_result)
    gap_resolutions: List[Dict[str, Any]] = []

    if precision_items:
        log(f"Deploying Wave 2 Precision Scouts for {len(precision_items)} targeted gap queries...")

        def build_wave2_scout(gap_item):
            q_str = gap_item["targeted_query"]
            gap_title = gap_item.get("title", "Data Gap")
            gap_type = gap_item.get("gap_type", "unverified_claim")
            conflicting = gap_item.get("conflicting_claims", "")
            description = gap_item.get("description", "")
            op_type = gap_item.get("search_operator_type", "keyword_precision")
            entities = gap_item.get("focus_entities", [])

            conflict_block = f"\nConflicting Claims to Investigate:\n{conflicting}\n" if conflicting else ""
            entities_block = f"\nFocus Entities / Benchmarks: {', '.join(entities)}\n" if entities else ""

            scout_prompt = (
                f"You are a Precision Research Scout resolving a specific research gap for: '{topic}'.\n\n"
                f"Target Gap: [{gap_type}] {gap_title}\n"
                f"Description: {description}\n"
                f"Target Search Query: `{q_str}` (Operator Type: {op_type})\n"
                f"{conflict_block}"
                f"{entities_block}\n"
                f"Instructions:\n"
                f"1. Execute `search_web` using the exact targeted search query: `{q_str}`.\n"
                f"2. Hunt specifically for concrete quantitative metrics (sample sizes, error rates, benchmark numbers, costs) or empirical resolution of conflicting claims.\n"
                f"3. Note whether the conflict is resolved by authoritative evidence, or whether a fundamental discrepancy remains between Tier 1 and Tier 2/3 sources.\n"
                f"4. Return structured summary, key findings with exact metrics, and source URLs."
            )
            return agent(
                prompt=scout_prompt,
                schema=SCOUT_SCHEMA,
                role=f"Precision Scout: {gap_title[:20]}",
                type_name="self",
                model="flash_lite"
            )

        try:
            wave2_results = await parallel(precision_items, build_wave2_scout)
        except Exception as e:
            log(f"Warning: Wave 2 precision scouts execution encountered an issue ({e}); proceeding with collected data.")
            wave2_results = []

        for gap_item, res in zip(precision_items, wave2_results or []):
            if not isinstance(res, dict):
                continue

            gap_title = gap_item.get("title", "Targeted Gap")
            evidence_dossier.append({
                "vector": f"Wave 2 Gap Resolution: {gap_title}",
                "summary": (
                    f"Gap Type: {gap_item.get('gap_type')}\n"
                    f"Target Query: {gap_item.get('targeted_query')}\n"
                    f"Investigated Gap: {gap_item.get('description')}\n\n"
                    f"Findings:\n{res.get('summary', '')}"
                ),
                "key_findings": res.get("key_findings", []),
                "gap_metadata": {
                    "gap_type": gap_item.get("gap_type"),
                    "title": gap_title,
                    "conflicting_claims": gap_item.get("conflicting_claims"),
                }
            })

            sources_field = res.get("sources", [])
            if isinstance(sources_field, list):
                for s in sources_field:
                    if isinstance(s, dict) and s.get("url"):
                        raw_sources.append(s)
            raw_sources.extend(extract_urls_from_text(res.get("summary", "")))

            # Evaluate gap resolution (resolved vs unresolved discrepancy)
            resolution = gap_analysis.evaluate_gap_resolution(gap_item, res)
            gap_resolutions.append(resolution)

        # Deep primary page extraction on Wave 2 targeted sources to resolve disputed metrics
        wave2_candidates: List[str] = []
        for res in (wave2_results or []):
            if isinstance(res, dict):
                sources_field = res.get("sources", [])
                if isinstance(sources_field, list):
                    for s in sources_field:
                        u = s.get("url") if isinstance(s, dict) else None
                        if u and u not in inspected_urls and eval_sources.is_valid_source_url(u):
                            wave2_candidates.append(u)
                            inspected_urls.add(u)
                for item in extract_urls_from_text(res.get("summary", "")):
                    u = item.get("url")
                    if u and u not in inspected_urls and eval_sources.is_valid_source_url(u):
                        wave2_candidates.append(u)
                        inspected_urls.add(u)

        if wave2_candidates:
            log(f"Deep Gap Inspection: inspecting up to {min(4, len(wave2_candidates))} targeted URLs to resolve disputed metrics...")
            for u in wave2_candidates[:4]:
                try:
                    gap_summary = read_page.extract_page_content_summary(u, max_chars=10000, timeout=6.0)
                except Exception as e:
                    log(f"Wave 2 page inspection error for {u}: {e}")
                    gap_summary = {"success": False}
                if gap_summary.get("success"):
                    deep_extracted_count += 1
                    gap_tables = gap_summary.get("tables", []) or []
                    total_tables_extracted += len(gap_tables)
                    gap_text = (gap_summary.get("text") or "")[:3000]
                    tbl_str = f"\n\n#### Extracted Primary Tables ({len(gap_tables)}):\n" + "\n\n".join(gap_tables) if gap_tables else ""
                    evidence_dossier.append({
                        "vector": f"Wave 2 Gap Resolution Table Evidence: {gap_summary.get('title') or u[:45]}",
                        "summary": (
                            f"Targeted Gap Primary Evidence: {u}\n"
                            f"Page Title: {gap_summary.get('title')}\n\n"
                            f"Direct Evidence Excerpt:\n{gap_text}"
                            f"{tbl_str}"
                        ),
                        "key_findings": [
                            f"Targeted deep page inspection completed for gap resolution on {u}",
                            f"Retrieved {len(gap_tables)} structured data tables for disputed metrics",
                        ],
                    })

        # Re-index citation map
        try:
            citation_map = eval_sources.build_citation_map(raw_sources, resolve_redirects=True)
        except Exception as e:
            log(f"Warning: Citation map update failed ({e}); falling back without redirect resolution.")
            citation_map = eval_sources.build_citation_map(raw_sources, resolve_redirects=False)
        dist = citation_map.get("credibility_distribution", {})
        log(f"Updated Citation Map: {dist.get('total', 0)} unique canonical sources indexed.")

    gap_resolution_summary = gap_analysis.format_gap_resolution_summary(gap_resolutions)
    log(f"Wave 2 Gap Resolution complete. Documented {len(gap_resolutions)} resolved/unresolved issues for Section 5.")

    # -------------------------------------------------------------
    # Phase 3: Grounded Draft Synthesis
    # -------------------------------------------------------------
    phase("Phase 3: Grounded Draft Synthesis")
    log("Synthesizing comprehensive, publication-grade report with strict inline citations...")

    # Build reference bibliography text for synthesizer prompt
    bib_reference_block = eval_sources.format_bibliography(citation_map)
    if not bib_reference_block:
        bib_reference_block = "No external citation sources recorded."
    # If bibliography exceeds context limits, take first 120 sources for prompt context
    bib_lines = bib_reference_block.split("\n")
    if len(bib_lines) > 120:
        bib_prompt_context = "\n".join(bib_lines[:120])
    else:
        bib_prompt_context = bib_reference_block

    synthesis_evidence_text = "\n\n".join([
        f"### {d.get('vector', 'Evidence')}\n{d.get('summary', '')}\nKey Findings:\n- " + "\n- ".join(d.get('key_findings', []))
        for d in evidence_dossier
    ]) if evidence_dossier else "No evidence dossier entries recorded."

    template_path = current_dir.parent / "templates" / "report_template.md"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as tf:
            report_template_sample = tf.read()
    else:
        report_template_sample = "Follow the standard 7-section publication-grade intelligence report structure."

    num_citations = len(citation_map.get("citations", {}))
    citation_range_guide = f"1 through {num_citations}" if num_citations > 0 else "None (cite sparingly or note ungrounded claims)"

    synth_prompt = (
        f"You are the Lead Research Synthesizer writing a definitive, publication-grade intelligence report on: '{topic}'.\n\n"
        f"GROUNDING STANDARDS (STRICT):\n"
        f"1. Every substantive assertion, quantitative metric, benchmark comparison, historical claim, and price MUST carry an inline citation anchor [N] referring to the index in the reference bibliography below.\n"
        f"2. Never hallucinate URLs or citation numbers. Only cite indices that exist in the bibliography below ({citation_range_guide}).\n"
        f"3. Zero Placeholders: Do NOT output placeholders like '[Insert ...]', '[N]', 'TODO', or 'TBD'. Every assertion must be concrete and grounded.\n"
        f"4. Prioritize hard empirical metrics (percentages, dollar amounts, latencies, sample sizes, architecture specs) over vague buzzwords.\n"
        f"5. Seamlessly incorporate the structured Markdown tables from the 'Deep Primary Page Evidence' and 'Wave 2 Gap Resolution Table Evidence' sections into the thematic analyses (Section 3) and comparative matrix (Section 4).\n\n"
        f"STRUCTURE REQUIREMENTS (Must follow all 7 sections):\n"
        f"## 1. Executive Briefing\n"
        f"- Key Takeaways: Bulleted high-impact empirical findings with citations [N].\n"
        f"- Decision Verdict: Clear, bottom-line strategic determination (adopt, invest, migrate, delay, avoid) with citations [N].\n"
        f"- Executive Narrative: High-density narrative spanning 2-4 comprehensive paragraphs with empirical metrics and citations [N].\n\n"
        f"## 2. Research Methodology & Evidence Scope\n"
        f"- Evidence Ingestion & Authority Tiers: Include the 4-tier distribution table:\n"
        f"  * Tier 1 (Primary Official): {dist.get('tier_1_count', 0)} ({dist.get('tier_1_pct', 0.0)}%)\n"
        f"  * Tier 2 (Testing & Journalism): {dist.get('tier_2_count', 0)} ({dist.get('tier_2_pct', 0.0)}%)\n"
        f"  * Tier 3 (Community Consensus): {dist.get('tier_3_count', 0)} ({dist.get('tier_3_pct', 0.0)}%)\n"
        f"  * Tier 4 (General Web): {dist.get('tier_4_count', 0)} ({dist.get('tier_4_pct', 0.0)}%)\n"
        f"  * Total Sources: {dist.get('total', 0)}\n"
        f"- Primary Page Inspection & DOM Table Extraction:\n"
        f"  * Deep Pages Audited: {deep_extracted_count} primary HTML documents fully parsed.\n"
        f"  * Structured Data Tables Extracted: {total_tables_extracted} multi-column markdown tables preserved directly from source DOMs.\n"
        f"  * Community Consensus Signals: {dist.get('community_consensus_count', 0)} discussions ingested from Reddit, GitHub issues, Stack Exchange, and review platforms.\n\n"
        f"## 3. Thematic Deep Dives\n"
        f"- Exhaustive domain-tailored sections with quantitative benchmark tables, mechanism breakdowns, and inline anchors [N].\n"
        f"- Must embed quantitative parameter / specification tables with columns: Component / Parameter | Specification / Mechanism | Observed Performance / Metric | Source Citation.\n\n"
        f"## 4. Comparative Matrix & Trade-Off Evaluation\n"
        f"- Side-by-side GFM table with columns:\n"
        f"  | Dimension / Option | Specs & Capabilities | Pricing / TCO | Benchmark Score / Throughput | Community Consensus | Best For | Citations |\n"
        f"- Trade-off evaluation & Pareto frontier narrative analyzing compromises and deployment fits [N].\n\n"
        f"## 5. Contradictions, Disputed Claims & Strategic Risks\n"
        f"- Strictly synthesize the Gap Resolution Audit below:\n"
        f"  * Disputed Data & Cross-Source Contradictions (Tier 1 official claims vs Tier 2 independent test lab measurements vs Tier 3 community consensus) [N].\n"
        f"  * Resolved Empirical Clarifications vs Persistent Discrepancies [N].\n"
        f"  * Strategic, Operational & Failure Mode Risks [N].\n\n"
        f"## 6. Strategic Outlook & Decision Playbook\n"
        f"- 12-24 Month Trajectory: Projected evolution and emerging standards [N].\n"
        f"- Actionable Recommendations by Persona:\n"
        f"  * For Technical Architects & Practitioners [N]\n"
        f"  * For Strategic Executives & Investors [N]\n"
        f"  * For Procurement & End-Users [N]\n"
        f"- Critical Unresolved Questions & Watchlist\n\n"
        f"## 7. Reference Bibliography\n"
        f"- Format: [N] **Title** — [URL](URL) (Tier X: Source Category: Domain)\n\n"
        f"GAP RESOLUTION AUDIT (RESOLVED FINDINGS VS UNRESOLVED DISCREPANCIES FOR SECTION 5):\n"
        f"{gap_resolution_summary}\n\n"
        f"AVAILABLE CITATION BIBLIOGRAPHY:\n{bib_prompt_context}\n\n"
        f"RESEARCH EVIDENCE DOSSIER:\n{synthesis_evidence_text}\n\n"
        f"Synthesize the full report in high-density, professional markdown."
    )

    try:
        synthesizer_agent = agent(
            prompt=synth_prompt,
            schema=SYNTHESIZER_SCHEMA,
            role="Lead Synthesizer",
            type_name="self",
            model="inherit"
        )
        draft_result = await synthesizer_agent
        if not isinstance(draft_result, dict):
            draft_result = {}
        draft_text = draft_result.get("report_markdown", "")
    except Exception as e:
        log(f"Warning: Lead Synthesizer encountered an issue ({e}); generating structured baseline synthesis.")
        draft_text = ""

    if not draft_text or len(draft_text.strip()) < 50:
        draft_text = (
            f"# {topic}: Deep Research Report\n\n"
            f"## 1. Executive Briefing\n\n"
            f"### Key Takeaways\n- Synthesized preliminary findings across {dist.get('total', 0)} sources.\n\n"
            f"### Decision Verdict\nStrategic evaluation for {topic}.\n\n"
            f"### Executive Narrative\nThis research report provides an in-depth empirical assessment of {topic}.\n\n"
            f"## 2. Research Methodology & Evidence Scope\n\n"
            f"Evaluated {dist.get('total', 0)} sources.\n\n"
            f"## 3. Thematic Deep Dives\n\n"
            f"Detailed inquiry vectors explored.\n\n"
            f"## 4. Comparative Matrix & Trade-Off Evaluation\n\n"
            f"| Dimension / Option | Specs & Capabilities | Pricing / TCO | Benchmark Score / Throughput | Community Consensus | Best For | Citations |\n"
            f"|---|---|---|---|---|---|---|\n"
            f"| Baseline Option | Core Architecture | Standard TCO | Nominal Performance | Consensus | Broad Adoption | [1] |\n\n"
            f"## 5. Contradictions, Disputed Claims & Strategic Risks\n\n"
            f"Cross-source analysis of empirical claims.\n\n"
            f"## 6. Strategic Outlook & Decision Playbook\n\n"
            f"Recommendations for technical practitioners and strategic decision makers.\n\n"
            f"## 7. Reference Bibliography\n\n"
            f"{bib_reference_block}\n"
        )

    log(f"Draft synthesized ({len(draft_text)} characters).")

    # -------------------------------------------------------------
    # Phase 4: Review & Validation Loop
    # -------------------------------------------------------------
    phase("Phase 4: Review & Validation Loop")
    log("Auditing draft against evidence dossier and validating citation references...")

    # Programmatic citation verification
    verification = eval_sources.verify_citations(draft_text, citation_map)
    log(f"Citation Verification -> Valid: {verification.get('valid')}, Cited: {len(verification.get('cited_indexes', []))}, "
        f"Missing: {len(verification.get('missing_indexes', []))}, Unused: {len(verification.get('unused_indexes', []))}")

    critic_prompt = (
        f"You are the Senior Research Critic and Verifier auditing a draft research report on: '{topic}'.\n\n"
        f"DRAFT REPORT:\n{draft_text}\n\n"
        f"CITATION VERIFICATION STATS:\n"
        f"- Valid: {verification.get('valid')}\n"
        f"- Missing Anchor IDs (used in text but missing from map): {verification.get('missing_indexes')}\n"
        f"- Errors: {verification.get('errors')}\n\n"
        f"AUDIT MANDATE:\n"
        f"1. Audit the draft for accuracy, rigorous prose, absence of hype, and proper citation anchoring [N].\n"
        f"2. Ensure all 7 sections are populated without placeholders (eliminate any '[Insert ...]', '[N]', 'TODO', 'TBD').\n"
        f"3. Verify Section 3 and Section 4 embed primary data tables and comparative matrix.\n"
        f"4. Verify Section 5 rigorously documents tensions between Tier 1 official claims, Tier 2 lab benchmarks, and Tier 3 community consensus.\n"
        f"5. If missing or invalid citation anchors exist, replace them with appropriate valid citations from the map (1 to {len(citation_map.get('citations', {}))}) or remove invalid brackets.\n"
        f"6. Ensure Section 7 contains the properly formatted reference bibliography: [N] **Title** — [URL](URL) (Tier X: Source Category: Domain).\n"
        f"7. Return corrected_report_markdown containing the polished, finalized report."
    )

    try:
        critic_agent = agent(
            prompt=critic_prompt,
            schema=CRITIC_SCHEMA,
            role="Critic / Verifier",
            type_name="self",
            model="inherit"
        )
        critic_result = await critic_agent
        if not isinstance(critic_result, dict):
            critic_result = {}
        final_report_markdown = critic_result.get("corrected_report_markdown", "") or draft_text
    except Exception as e:
        log(f"Warning: Critic / Verifier execution failed or timed out ({e}); retaining draft report.")
        final_report_markdown = draft_text

    if not final_report_markdown or len(final_report_markdown.strip()) < 50:
        final_report_markdown = draft_text

    # Programmatically guarantee complete, clean Section 7 Reference Bibliography
    if citation_map.get("citations"):
        final_report_markdown = eval_sources.ensure_report_bibliography(final_report_markdown, citation_map)

    # Re-verify final report citations
    final_verification = eval_sources.verify_citations(final_report_markdown, citation_map)
    log(f"Final Report Audit complete. Final citation validity: {final_verification['valid']}, "
        f"Total inline anchors: {final_verification['total_inline_occurrences']}, "
        f"Unique cited sources: {len(final_verification['cited_indexes'])}/{dist.get('total', 0)}")
    if not final_verification['valid']:
        log(f"Warning: Citation verification issues remaining: {final_verification['errors']}")

    # -------------------------------------------------------------
    # Deliverables: Write to Workspace & Conversation Artifact
    # -------------------------------------------------------------
    topic_slug = re.sub(r"[^a-zA-Z0-9_\-]+", "-", topic.lower()).strip("-")[:60]
    filename = f"{topic_slug}-deep-research.md"
    workspace_dir = WORKSPACES[0] if (WORKSPACES and len(WORKSPACES) > 0) else os.getcwd()
    output_path = os.path.join(workspace_dir, filename)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_report_markdown)
        log(f"SUCCESS: Report saved to workspace: {output_path}")
    except Exception as e:
        log(f"Warning: Failed to write to workspace path {output_path}: {e}")

    # Write conversation artifact if CONVERSATION_ID is present in globals or env
    conv_id = globals().get("CONVERSATION_ID") or os.environ.get("CONVERSATION_ID")
    artifact_path = None
    if conv_id:
        try:
            app_data_dir = (
                globals().get("DEEP_RESEARCH_SCRATCH")
                or os.environ.get("DEEP_RESEARCH_SCRATCH")
                or "/tmp/opencode/deep-research"
            )
            artifact_dir = Path(app_data_dir) / "brain" / str(conv_id)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_file = artifact_dir / filename
            with open(artifact_file, "w", encoding="utf-8") as af:
                af.write(final_report_markdown)
            artifact_path = str(artifact_file)
            log(f"SUCCESS: Conversation artifact saved: {artifact_path}")
        except Exception as e:
            log(f"Warning: Failed to write conversation artifact: {e}")

    log(f"SUCCESS: Report saved to {output_path}")
    print(f"REPORT_PATH: {output_path}")
    if artifact_path:
        print(f"ARTIFACT_PATH: {artifact_path}")
    print(f"TOTAL_SOURCES: {dist.get('total', 0)}")
    print(f"TIER_1_PCT: {dist.get('tier_1_pct', 0.0)}%")
    print(f"VERIFICATION_STATUS: {'PASSED' if final_verification['valid'] else 'WARNING'}")


# Execute top-level await
await main()
