#!/usr/bin/env python3
"""
Second-Order Gap Analysis & Precision Queries for Deep Research.
Modeled after Gemini Web Deep Research and Stanford STORM.

Provides:
  1. GAP_ANALYST_SCHEMA for structured multi-hop reasoning.
  2. Gap schema validation and taxonomy categorization.
  3. Search operator detection (exact quotes, site:, filetype:pdf, comparative pairs).
  4. Lead Gap Analyst prompt construction ingesting Wave 1 findings and Phase 1.6 tables.
  5. Gap resolution evaluator tracking resolved findings vs unresolved discrepancies for Section 5.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Supported Gap Types (Taxonomy)
VALID_GAP_TYPES: Tuple[str, ...] = (
    "quantitative_deficit",
    "contradiction",
    "unverified_claim",
    "missing_subtopic",
)

# Supported Search Operator Types
VALID_OPERATOR_TYPES: Tuple[str, ...] = (
    "exact_quote",
    "site_restricted",
    "filetype_pdf",
    "comparative_pair",
    "keyword_precision",
)

# JSON Schema for Lead Gap Analyst in Phase 2
GAP_ANALYST_SCHEMA: Dict[str, Any] = {
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


def detect_search_operator(query: str) -> str:
    """
    Detects the primary search operator type present in a precision search query.
    Recognizes:
      - 'filetype_pdf': filetype:pdf or ext:pdf
      - 'site_restricted': site:example.com or site:.gov
      - 'comparative_pair': 'X vs Y', 'X versus Y', or 'X compared to Y'
      - 'exact_quote': queries containing quoted phrases ("...")
      - 'keyword_precision': high-specificity domain keyword query
    """
    if not query or not isinstance(query, str):
        return "keyword_precision"

    q_strip = query.strip()

    # 1. filetype:pdf / ext:pdf operator
    if re.search(r"\b(?:filetype|ext):pdf\b", q_strip, re.IGNORECASE):
        return "filetype_pdf"

    # 2. site: restriction operator
    if re.search(r"\bsite:\S+", q_strip, re.IGNORECASE):
        return "site_restricted"

    # 3. Comparative pair patterns ("A" vs "B", A versus B, compared to)
    if re.search(r'(?:".+?"|\b[\w\-]+)\s+(?:vs\.?|versus|compared to)\s+(?:".+?"|\b[\w\-]+)', q_strip, re.IGNORECASE):
        return "comparative_pair"

    # 4. Exact phrase matching with quotes
    if re.search(r'"[^"]{2,}"', q_strip):
        return "exact_quote"

    return "keyword_precision"


def validate_gap_item(gap: Any) -> Tuple[bool, List[str]]:
    """
    Validates a single gap entry against the required schema constraints.
    """
    errors: List[str] = []
    if not isinstance(gap, dict):
        return False, ["Gap item must be a JSON object (dict)."]

    # Required fields
    for field in ("gap_type", "title", "description", "targeted_query"):
        val = gap.get(field)
        if not val or not isinstance(val, str) or not val.strip():
            errors.append(f"Missing or empty required field '{field}'.")

    gap_type = gap.get("gap_type")
    if gap_type and gap_type not in VALID_GAP_TYPES:
        errors.append(f"Invalid gap_type '{gap_type}'. Must be one of {VALID_GAP_TYPES}.")

    # Optional fields validation
    op_type = gap.get("search_operator_type")
    if op_type is not None:
        if not isinstance(op_type, str) or op_type not in VALID_OPERATOR_TYPES:
            errors.append(f"Invalid search_operator_type '{op_type}'. Must be one of {VALID_OPERATOR_TYPES}.")

    entities = gap.get("focus_entities")
    if entities is not None:
        if not isinstance(entities, list) or not all(isinstance(e, str) for e in entities):
            errors.append("Field 'focus_entities' must be a list of strings.")

    conflicting = gap.get("conflicting_claims")
    if conflicting is not None and not isinstance(conflicting, str):
        errors.append("Field 'conflicting_claims' must be a string if provided.")

    return len(errors) == 0, errors


def validate_gap_analysis(gap_data: Any) -> Tuple[bool, List[str]]:
    """
    Validates the complete Lead Gap Analyst response payload.
    """
    errors: List[str] = []
    if not isinstance(gap_data, dict):
        return False, ["Gap analysis result must be a JSON object (dict)."]

    critique = gap_data.get("executive_critique")
    if not critique or not isinstance(critique, str) or not critique.strip():
        errors.append("Field 'executive_critique' is required and must be a non-empty string.")

    gaps = gap_data.get("identified_gaps")
    if not isinstance(gaps, list):
        errors.append("Field 'identified_gaps' must be a list of gap items.")
        return False, errors

    if len(gaps) == 0:
        errors.append("Field 'identified_gaps' must contain at least 1 identified gap.")

    for idx, item in enumerate(gaps):
        ok, item_errors = validate_gap_item(item)
        if not ok:
            for err in item_errors:
                errors.append(f"Gap [{idx}]: {err}")

    return len(errors) == 0, errors


def categorize_gaps(gaps: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorizes identified gaps into taxonomy buckets:
      - quantitative_deficit
      - contradiction
      - unverified_claim
      - missing_subtopic
    """
    categorized: Dict[str, List[Dict[str, Any]]] = {
        "quantitative_deficit": [],
        "contradiction": [],
        "unverified_claim": [],
        "missing_subtopic": [],
    }

    for g in gaps:
        if not isinstance(g, dict):
            continue
        g_type = g.get("gap_type", "unverified_claim")
        if g_type not in categorized:
            categorized[g_type] = []
        categorized[g_type].append(g)

    return categorized


def extract_precision_queries(gap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extracts normalized precision scout query targets from identified gaps.
    Infers search_operator_type if absent or verifies operator compatibility.
    """
    if not isinstance(gap_data, dict):
        return []

    gaps = gap_data.get("identified_gaps", [])
    extracted: List[Dict[str, Any]] = []

    for item in gaps:
        if not isinstance(item, dict):
            continue
        q = item.get("targeted_query", "").strip()
        if not q:
            continue

        op_type = item.get("search_operator_type")
        if not op_type or op_type not in VALID_OPERATOR_TYPES:
            op_type = detect_search_operator(q)

        extracted.append({
            "gap_type": item.get("gap_type", "unverified_claim"),
            "title": item.get("title", "Data Gap"),
            "description": item.get("description", ""),
            "conflicting_claims": item.get("conflicting_claims", ""),
            "targeted_query": q,
            "search_operator_type": op_type,
            "focus_entities": item.get("focus_entities", []),
        })

    return extracted


def build_gap_analyst_prompt(
    topic: str,
    evidence_dossier: List[Dict[str, Any]],
    citation_dist: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Builds a rigorous prompt for the Lead Gap Analyst agent.
    Explicitly structures initial evidence into:
      1. Wave 1 Scout Findings
      2. Phase 1.6 Deep Primary Page Evidence & Extracted Tables
      3. Authority Distribution
    Mandates multi-hop reasoning over quantitative deficits, contradictions, and precision queries.
    """
    # Separate Wave 1 scout breadth findings from Phase 1.6 deep primary evidence
    wave1_sections: List[str] = []
    deep_table_sections: List[str] = []

    for d in evidence_dossier:
        vec = d.get("vector", "Evidence")
        summary = d.get("summary", "")
        findings = d.get("key_findings", [])
        findings_str = "\n- ".join(findings[:6]) if findings else "None listed"

        block = f"#### {vec}\n{summary[:1600]}\nKey Findings:\n- {findings_str}"

        if "Deep Primary Page Evidence" in vec or "Extracted Primary Tables" in summary:
            deep_table_sections.append(block)
        else:
            wave1_sections.append(block)

    wave1_preview = "\n\n".join(wave1_sections) if wave1_sections else "No Wave 1 evidence recorded."
    deep_preview = "\n\n".join(deep_table_sections) if deep_table_sections else "No deep primary tables extracted."

    dist_summary = ""
    if citation_dist:
        dist_summary = (
            f"Evaluated Source Authority Distribution:\n"
            f"- Total Sources: {citation_dist.get('total', 0)}\n"
            f"- Tier 1 (Official / Academic / Regulatory): {citation_dist.get('tier_1_count', 0)} ({citation_dist.get('tier_1_pct', 0.0)}%)\n"
            f"- Tier 2 (Testing Labs / Investigative Journalism): {citation_dist.get('tier_2_count', 0)} ({citation_dist.get('tier_2_pct', 0.0)}%)\n"
            f"- Tier 3 (Practitioner Consensus / Communities): {citation_dist.get('tier_3_count', 0)} ({citation_dist.get('tier_3_pct', 0.0)}%)\n"
            f"- Tier 4 (General Web): {citation_dist.get('tier_4_count', 0)} ({citation_dist.get('tier_4_pct', 0.0)}%)\n"
            f"- Community Consensus Signals: {citation_dist.get('community_consensus_count', 0)}\n\n"
        )

    prompt = (
        f"You are the Lead Gap Analyst conducting second-order verification and multi-hop reasoning on: '{topic}'.\n\n"
        f"EVALUATED EVIDENCE DOSSIER:\n\n"
        f"=== SECTION A: WAVE 1 BREADTH SCOUT FINDINGS ===\n"
        f"{wave1_preview}\n\n"
        f"=== SECTION B: PHASE 1.6 DEEP PRIMARY TABLES & EXCERPTS ===\n"
        f"{deep_preview}\n\n"
        f"{dist_summary}"
        f"ANALYSIS MANDATE (SECOND-ORDER GAP DISCOVERY):\n"
        f"Perform an exhaustive audit of the evidence dossier to identify critical deficits that prevent a definitive publication-grade assessment.\n"
        f"Specifically audit:\n"
        f"1. Quantitative Deficits: Identify missing empirical baselines, missing sample sizes, unstated unit economics/cost curves, missing latency numbers, or unmeasured failure rates.\n"
        f"2. Cross-Source Contradictions: Detect direct discrepancies between Tier 1 manufacturer claims vs Tier 2 independent benchmark results, or official specifications vs Tier 3 community complaint patterns.\n"
        f"3. Unverified Claims & Generalizations: Call out marketing assertions or broad claims that lack primary empirical grounding.\n"
        f"4. Missing Subtopics: Identify critical facets or alternative architectures not yet addressed.\n\n"
        f"PRECISION QUERY GENERATION RULES:\n"
        f"For each identified gap, generate 1 highly targeted search query utilizing advanced operators:\n"
        f"- `\"...\"` (exact quotes): Pin exact terminology, model numbers, or benchmark suites.\n"
        f"- `site:...`: Target primary registries, lab domains, or preprint servers (e.g. site:arxiv.org, site:github.com, site:fda.gov).\n"
        f"- `filetype:pdf`: Retrieve whitepapers, datasheets, or peer-reviewed PDFs.\n"
        f"- Comparative pairs: e.g. '\"Entity A\" vs \"Entity B\" benchmark latency'.\n"
        f"- Keyword precision: Multi-term technical queries avoiding generic search terms.\n\n"
        f"Generate between 3 and 5 high-impact gaps in identified_gaps with executive_critique."
    )
    return prompt


def evaluate_gap_resolution(gap: Dict[str, Any], scout_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates whether Wave 2 precision scout findings resolved the identified gap,
    or whether an active contradiction/discrepancy remains.
    """
    gap_type = gap.get("gap_type", "unverified_claim")
    gap_title = gap.get("title", "Target Gap")
    conflicting = gap.get("conflicting_claims", "")
    query = gap.get("targeted_query", "")

    summary = scout_result.get("summary", "") if isinstance(scout_result, dict) else ""
    key_findings = scout_result.get("key_findings", []) if isinstance(scout_result, dict) else []

    # Heuristic detection for unresolved vs resolved
    # Indicators of unresolved discrepancy / active controversy:
    conflict_markers = [
        "contradict", "discrepan", "dispute", "conflicting", "inconsistent",
        "diverge", "unresolved", "mixed results", "claims differ", "versus official"
    ]
    summary_lower = summary.lower()
    has_conflict_signal = any(m in summary_lower for m in conflict_markers)

    # If it was originally a contradiction or has active conflict signals
    if gap_type == "contradiction" and has_conflict_signal:
        status = "unresolved_discrepancy"
        resolution_notes = (
            f"Sources exhibit persistent discrepancies. "
            f"Official/manufacturer claims remain in tension with independent testing/community evidence."
        )
    elif len(key_findings) > 0 or len(summary) > 100:
        status = "resolved"
        resolution_notes = f"Retrieved verified evidence and empirical metrics addressing '{gap_title}'."
    else:
        status = "unresolved_discrepancy"
        resolution_notes = f"Insufficient empirical data retrieved to resolve gap."

    return {
        "gap_type": gap_type,
        "title": gap_title,
        "status": status,
        "targeted_query": query,
        "conflicting_claims": conflicting,
        "findings": key_findings,
        "summary": summary,
        "resolution_notes": resolution_notes,
    }


def format_gap_resolution_summary(resolutions: List[Dict[str, Any]]) -> str:
    """
    Formats a structured Markdown summary of resolved findings vs unresolved discrepancies.
    Designed for seamless integration into the synthesizer prompt for Section 5:
    'Contradictions, Disputed Claims & Strategic Risks'.
    """
    if not resolutions:
        return "No secondary gap resolutions recorded."

    resolved_items = [r for r in resolutions if r.get("status") == "resolved"]
    unresolved_items = [r for r in resolutions if r.get("status") != "resolved"]

    lines: List[str] = [
        "### Wave 2 Gap Analysis & Verification Audit",
        f"- Total Gaps Investigated: {len(resolutions)}",
        f"- Resolved Quantitative Deficits & Verified Claims: {len(resolved_items)}",
        f"- Active Discrepancies & Contradictions: {len(unresolved_items)}",
        "",
        "#### A. Resolved Gaps & Empirical Clarifications:"
    ]

    if resolved_items:
        for r in resolved_items:
            lines.append(f"##### [{r.get('gap_type', 'gap').upper()}] {r.get('title')}")
            lines.append(f"- Query: `{r.get('targeted_query')}`")
            lines.append(f"- Resolution: {r.get('resolution_notes')}")
            findings = r.get("findings", [])
            if findings:
                lines.append("- Empirical Findings:")
                for f in findings[:3]:
                    lines.append(f"  * {f}")
            lines.append("")
    else:
        lines.append("None recorded.\n")

    lines.append("#### B. Unresolved Contradictions & Disputed Claims (MUST FEATURE IN SECTION 5):")
    if unresolved_items:
        for r in unresolved_items:
            lines.append(f"##### [ACTIVE DISCREPANCY] {r.get('title')}")
            lines.append(f"- Target Query: `{r.get('targeted_query')}`")
            if r.get("conflicting_claims"):
                lines.append(f"- Conflicting Source Claims: {r.get('conflicting_claims')}")
            lines.append(f"- Audit Status: {r.get('resolution_notes')}")
            summary = r.get("summary", "")
            if summary:
                lines.append(f"- Analysis Excerpt: {summary[:400]}...")
            lines.append("")
    else:
        lines.append("All identified contradictions were resolved by primary source empirical metrics.\n")

    return "\n".join(lines)
