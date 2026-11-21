#!/usr/bin/env python3
"""
Adaptive Domain Detection and Dynamic Inquiry Vector Generation for Deep Research.
Modeled after Gemini Web Deep Research and Stanford STORM.
Supports:
  1. Phase 0 Lead Research Planner schema and prompt generation for LLM-driven vector synthesis.
  2. Strict vector validation enforcing MECE orthogonality, concrete queries, and primary sources.
  3. Resilient offline fallback planner spanning diverse real-world domains without software bias.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Supported domain taxonomy
SUPPORTED_DOMAINS = (
    "biomedical_health",
    "culinary_food_science",
    "geopolitical_macro",
    "consumer_hardware",
    "business_finance",
    "policy_legal",
    "technology_architecture",
    "lifestyle_travel_general",
    "universal_inquiry",
)

# Legacy domain aliases for backward compatibility
DOMAIN_ALIASES: Dict[str, str] = {
    "product_comparison": "consumer_hardware",
    "market_industry": "business_finance",
    "company_finance": "business_finance",
    "policy_governance": "policy_legal",
}

DOMAIN_METADATA: Dict[str, Dict[str, str]] = {
    "biomedical_health": {
        "name": "Clinical Pharmacokinetics & Biomedical Sciences",
        "description": "Drug mechanisms, clinical trials (Phase 1-3), pharmacokinetics, safety profiles, FDA/EMA status, and health economics.",
    },
    "culinary_food_science": {
        "name": "Gastronomy & Culinary Food Science",
        "description": "Ingredient chemistry, fermentation dynamics, thermal mechanics, regional authenticity standards (DOP/STG), and sensory analysis.",
    },
    "geopolitical_macro": {
        "name": "Geopolitics, Defense & Maritime Strategy",
        "description": "Strategic chokepoints, sovereignty disputes, military force posture, supply chain vulnerabilities, and crisis escalation pathways.",
    },
    "consumer_hardware": {
        "name": "Consumer Hardware & Electronics",
        "description": "Hardware architecture, empirical benchmarks, teardowns, repairability, software lifecycle, and buying verdicts.",
    },
    "business_finance": {
        "name": "Corporate Finance & Market Intelligence",
        "description": "Business models, unit economics, SEC 10-K filings, free cash flow, competitive moats, and valuation multiples.",
    },
    "policy_legal": {
        "name": "Public Policy & Regulatory Governance",
        "description": "Statutory genesis, legal compliance mandates, supervisory enforcement, economic impact, and international harmonization.",
    },
    "technology_architecture": {
        "name": "Deep Software & Systems Architecture",
        "description": "Protocols, state machine replication, latency benchmarks, concurrency limits, system failure modes, and technical roadmaps.",
    },
    "lifestyle_travel_general": {
        "name": "Lifestyle, Travel & Cultural Logistics",
        "description": "Field itineraries, logistics, budgeting, cultural customs, seasonal considerations, and local nuances.",
    },
    "universal_inquiry": {
        "name": "Universal Empirical Inquiry",
        "description": "General domain-agnostic investigation spanning foundational principles, material composition, empirical metrics, economics, vulnerabilities, and expert consensus.",
    },
}

# Lead Research Planner JSON Schema for Phase 0
PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "domain_analysis": {
            "type": "string",
            "description": "Semantic domain categorization and nature of the inquiry (e.g. clinical pharmacology, geopolitical conflict, culinary science, consumer hardware, etc.)."
        },
        "scoping_rationale": {
            "type": "string",
            "description": "Explanation of how the inquiry vectors span the topic orthogonally without overlapping."
        },
        "vectors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique snake_case slug identifying the vector."
                    },
                    "name": {
                        "type": "string",
                        "description": "Descriptive, domain-specific title of the vector."
                    },
                    "focus": {
                        "type": "string",
                        "description": "Nuanced research criteria, specific entities, quantitative metrics, mechanisms, and empirical questions to investigate."
                    },
                    "search_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2 to 4 high-yield, specific targeted search queries with exact entity names, metrics, and search operators."
                    },
                    "primary_source_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific authoritative sources to prioritize (e.g. peer-reviewed journals, regulatory filings, clinical trial registries, industry benchmark databases, teardowns, archives)."
                    }
                },
                "required": ["id", "name", "focus", "search_queries", "primary_source_types"]
            },
            "minItems": 6,
            "maxItems": 8
        }
    },
    "required": ["domain_analysis", "scoping_rationale", "vectors"]
}


def build_planner_prompt(topic: str, scope: str = "", user_hints: Optional[str] = None) -> str:
    """
    Constructs an architectural prompt for the Phase 0 Lead Research Planner agent.
    Instructs the LLM to perform deep semantic decomposition native to the inquiry domain
    without rigid software engineering templates or mad-libs format strings.
    """
    clean_topic = str(topic or "").strip()
    clean_scope = str(scope or "").strip()
    hints_text = f"\nUser Scoping Hints & Desired Angles: {user_hints}" if user_hints else ""

    return (
        f"You are the Lead Research Architect and Planner for an autonomous deep research investigation.\n"
        f"Topic: '{clean_topic}'\n"
        f"Scope / Objectives: '{clean_scope}'{hints_text}\n\n"
        f"MISSION:\n"
        f"Deconstruct this topic into 6 to 8 mutually exclusive, collectively exhaustive (MECE) orthogonal inquiry vectors.\n"
        f"Your decomposition must be native to the subject matter's specific domain (e.g. culinary science, clinical pharmacokinetics, geopolitical strategy, consumer electronics, corporate finance, or systems engineering).\n\n"
        f"CRITICAL REQUIREMENTS:\n"
        f"1. ZERO TEMPLATE BIAS: Never force software engineering frameworks (e.g., CAP theorem, CVEs, microservices, runtime memory management) onto non-software topics like food, medicine, geopolitics, or art.\n"
        f"2. DOMAIN-SPECIFIC RIGOR: Synthesize criteria, empirical questions, and metrics tailored specifically to '{clean_topic}'.\n"
        f"   - For clinical/pharma: molecular mechanisms, Phase 1-3 trials, pharmacokinetics, adverse reactions, FDA/EMA status, pricing/reimbursement.\n"
        f"   - For culinary/food: food chemistry & microbiology, traditional methods, thermal dynamics & oven specs, regional appellations (DOP/STG), sensory/texture profiles, common flaws.\n"
        f"   - For geopolitics: trade flows & chokepoints, treaties & legal claims, military force posture & deterrence, economic sanctions & supply cascades, diplomatic alliances, crisis escalation pathways.\n"
        f"   - For consumer hardware: hardware architecture, empirical benchmarks (battery/thermals), teardown & repairability, software ecosystem/support, real-world user reliability, price/value verdict.\n"
        f"   - For systems engineering: protocols & state management, empirical latency/throughput benchmarks, operational limits & failure modes, developer tooling, security threat models.\n"
        f"   - For general/other: foundational principles, structural composition, empirical benchmarks, economic factors, critical failure modes, expert consensus roadmap.\n"
        f"3. ACTIONABLE SEARCH QUERIES: For each vector, produce 2 to 4 high-yield, specific targeted search queries using exact entity names, quotes, operators, and metrics.\n"
        f"4. AUTHORITATIVE SOURCES: Explicitly list the exact primary source types to prioritize (e.g., PubMed, ClinicalTrials.gov, SEC 10-K, IEEE, iFixit, UNCLOS registries, official standards)."
    )


def validate_vectors(vectors: Any) -> Tuple[bool, List[str]]:
    """
    Validates that a list of inquiry vectors meets the rigorous structural
    and content standards of deep research.
    Returns (is_valid, list_of_error_strings).
    """
    errors: List[str] = []
    if not isinstance(vectors, list):
        return False, ["Vectors must be a list."]

    if len(vectors) < 6 or len(vectors) > 8:
        errors.append(f"Vector count must be between 6 and 8 (received {len(vectors)}).")

    seen_ids: Set[str] = set()

    for idx, v in enumerate(vectors, 1):
        if not isinstance(v, dict):
            errors.append(f"Vector {idx} must be a dictionary.")
            continue

        vec_id = str(v.get("id", "")).strip()
        if not vec_id:
            errors.append(f"Vector {idx} missing non-empty 'id'.")
        elif vec_id in seen_ids:
            errors.append(f"Duplicate vector id '{vec_id}' at index {idx}.")
        else:
            seen_ids.add(vec_id)

        name = str(v.get("name", "")).strip()
        if not name:
            errors.append(f"Vector {idx} missing non-empty 'name'.")

        focus = str(v.get("focus", "")).strip()
        if not focus or len(focus) < 20:
            errors.append(f"Vector {idx} ('{name}') 'focus' must be at least 20 characters long.")

        queries = v.get("search_queries")
        if not isinstance(queries, list) or len(queries) < 2:
            errors.append(f"Vector {idx} ('{name}') 'search_queries' must be a list of at least 2 queries.")
        else:
            for q_idx, q in enumerate(queries, 1):
                if not isinstance(q, str) or not q.strip():
                    errors.append(f"Vector {idx} query {q_idx} must be a non-empty string.")

        sources = v.get("primary_source_types")
        if not sources:
            errors.append(f"Vector {idx} ('{name}') missing 'primary_source_types'.")
        elif isinstance(sources, list):
            if len(sources) < 1:
                errors.append(f"Vector {idx} ('{name}') 'primary_source_types' list is empty.")
        elif not isinstance(sources, str):
            errors.append(f"Vector {idx} ('{name}') 'primary_source_types' must be a list or string.")

    return len(errors) == 0, errors


# Domain keyword and intent patterns for offline classification
DOMAIN_PATTERNS: Dict[str, List[Tuple[str, int]]] = {
    "culinary_food_science": [
        (r"\b(pizza|neapolitan|sourdough|fermentation|dough|baking|bread)\b", 6),
        (r"\b(recipe|culinary|chef|cooking|gastronomy|ingredient|hydration)\b", 5),
        (r"\b(wine|vineyard|brewing|roasting|coffee|cheese|flavor|taste)\b", 4),
        (r"\b(dop|doc|stg|avpn|oven|crumb|mouthfeel|crust)\b", 5),
    ],
    "biomedical_health": [
        (r"\b(glp[\s\-]1|semaglutide|tirzepatide|ozempic|wegovy|mounjaro|zepbound)\b", 7),
        (r"\b(pharmacokinetics|pharmacodynamics|pharmacology|efficacy|clinical\s+trials?)\b", 6),
        (r"\b(phase\s+[1-3]|rct|adverse\s+events|contraindications|dosage|fda\s+approval)\b", 5),
        (r"\b(oncology|vaccine|antibody|immunotherapy|therapeutics?|cardiovascular)\b", 5),
        (r"\b(drug|medication|reimbursement|icer|orange\s+book)\b", 4),
    ],
    "geopolitical_macro": [
        (r"\b(taiwan\s+strait|south\s+china\s+sea|strait\s+of\s+hormuz|chokepoint)\b", 7),
        (r"\b(blockade|maritime\s+shipping|naval\s+quarantine|force\s+posture)\b", 6),
        (r"\b(sovereignty|unclos|sanctions|deterrence|nato|treaty|territorial)\b", 5),
        (r"\b(military|defense|escalation|geopolitical|foreign\s+policy|trade\s+corridor)\b", 4),
    ],
    "consumer_hardware": [
        (r"\b(macbook|thinkpad|pixel\s+\d|galaxy\s+s\d|iphone|rtx\s+\d\d\d\d|intel|amd|nvidia|qualcomm)\b", 6),
        (r"\b(headphones|earbuds|laptop|smartphone|smartwatch|monitor|camera|oled|gpu|cpu|soc)\b", 5),
        (r"\b(battery\s+life|hardware\s+teardown|ifixit|geekbench|cinebench|repairability\s+score)\b", 5),
        (r"\b(display\s+panel|thermal\s+throttling|chassis|firmware\s+updates?|consumer\s+electronics)\b", 4),
    ],
    "business_finance": [
        (r"\b(10[\s\-]k|10[\s\-]q|sec\s+filing|balance\s+sheet|cash\s+flow)\b", 6),
        (r"\b(ebitda|gross\s+margins?|operating\s+margin|valuation\s+multiples?)\b", 5),
        (r"\b(quarterly\s+earnings|revenue\s+streams?|unit\s+economics|tam|cagr)\b", 5),
        (r"\b(market\s+size|market\s+share|ipo|stock\s+performance|investor\s+relations)\b", 4),
    ],
    "policy_legal": [
        (r"\b(gdpr|hipaa|eu\s+ai\s+act|ai\s+act|dmca|sox|pci[\s\-]dss|ccpa|dora)\b", 6),
        (r"\b(compliance\s+obligations?|regulatory\s+compliance|enforcement\s+penalties?)\b", 5),
        (r"\b(statutory\s+authority|antitrust|supervisory\s+body|sanctions?)\b", 5),
        (r"\b(regulation|regulations|regulatory|statute|directive|jurisdiction)\b", 4),
    ],
    "technology_architecture": [
        (r"\b(distributed\s+systems?|consensus\s+protocol|raft|paxos|byzantine)\b", 6),
        (r"\b(storage\s+engine|database\s+internals|query\s+planner|compiler\s+design)\b", 6),
        (r"\b(low\s+latency|cache\s+coherence|concurrency\s+control|kernel\s+internals)\b", 5),
        (r"\b(transformer\s+architecture|llm\s+inference|cuda\s+kernel|microservices)\b", 5),
    ],
    "lifestyle_travel_general": [
        (r"\b(itinerary|travel\s+guide|city\s+guide|places\s+to\s+visit|things\s+to\s+do)\b", 6),
        (r"\b(backpacking|solo\s+travel|day\s+trip|vacation\s+in|cost\s+of\s+living\s+in)\b", 5),
        (r"\b(travel|tourism|flight|hotel|airbnb|sightseeing|packing\s+list)\b", 4),
    ],
}

# Domain-specific offline fallback vector templates (zero cross-domain jargon)
OFFLINE_VECTOR_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "culinary_food_science": [
        {
            "id": "historical_heritage",
            "name": "Historical Origins, Cultural Heritage & Traditional Standards",
            "focus": "Historical evolution, cultural origins, traditional preparation customs, and regulatory designations (e.g. STG, DOP, DOC) of {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" history cultural origin traditional preparation',
                '"{topic}" authentic standards specification STG DOP registry'
            ],
            "primary_source_types": ["Culinary historical archives", "Protected Designation of Origin (DOP/STG) registries", "Culinary heritage foundations"]
        },
        {
            "id": "ingredient_chemistry",
            "name": "Ingredient Science, Chemistry & Bio-Fermentation",
            "focus": "Biochemical interactions, hydration ratios, yeast/bacterial activity, fermentation kinetics, and protein/gluten matrix development in {topic}.",
            "search_queries": [
                '"{topic}" fermentation kinetics hydration ratio yeast enzymatic activity',
                '"{topic}" flour protein content gluten development biochemistry'
            ],
            "primary_source_types": ["Peer-reviewed food chemistry journals", "Cereal science research publications", "Biochemical food science studies"]
        },
        {
            "id": "technique_thermal_dynamics",
            "name": "Preparation Technique, Thermal Dynamics & Equipment Specs",
            "focus": "Physical preparation steps, heat transfer mechanics (conduction, convection, radiation), oven/cooking temperature profiles, and tool specifications for {topic}.",
            "search_queries": [
                '"{topic}" oven temperature thermal transfer conductive heat floor',
                '"{topic}" preparation technique equipment specifications bake time'
            ],
            "primary_source_types": ["Culinary engineering studies", "Professional kitchen technical manuals", "Thermal food processing research"]
        },
        {
            "id": "regional_variations",
            "name": "Regional Variations, Authenticity & Appellation Rules",
            "focus": "Geographic adaptations, stylistic variations, authentic vs commercial modifications, and legal protection guidelines for {topic}.",
            "search_queries": [
                '"{topic}" regional variations authentic vs contemporary styles',
                '"{topic}" geographical appellation rules authenticity criteria'
            ],
            "primary_source_types": ["Regional agricultural boards", "Gastronomy trade associations", "Food culture field research"]
        },
        {
            "id": "sensory_texture_flavor",
            "name": "Sensory Evaluation, Texture Profile & Flavor Chemistry",
            "focus": "Organoleptic assessment, crumb structure, mouthfeel, aromatic volatiles, Maillard reaction browning, and taste balance for {topic}.",
            "search_queries": [
                '"{topic}" sensory evaluation crumb structure texture mouthfeel',
                '"{topic}" flavor chemistry aroma compounds Maillard browning'
            ],
            "primary_source_types": ["Sensory analysis panels", "Food texture profile studies", "Flavor chemistry literature"]
        },
        {
            "id": "troubleshooting_innovations",
            "name": "Common Flaws, Troubleshooting & Contemporary Innovations",
            "focus": "Common preparation defects, structural collapses, over/under-fermentation signs, troubleshooting remedies, and contemporary progressive adaptations in {topic}.",
            "search_queries": [
                '"{topic}" common mistakes troubleshooting defects fermentation flaws',
                '"{topic}" modern innovations progressive techniques adaptations'
            ],
            "primary_source_types": ["Master artisan technical guides", "Baking and gastronomy troubleshooting manuals", "Culinary laboratory reviews"]
        },
    ],

    "biomedical_health": [
        {
            "id": "mechanism_pathways",
            "name": "Mechanism of Action & Biological Pathways",
            "focus": "Molecular pharmacology, receptor binding affinity, downstream cellular signaling pathways, and physiological mechanisms in {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" mechanism of action receptor binding affinity pathways',
                '"{topic}" molecular pharmacology biological targets cellular cascade'
            ],
            "primary_source_types": ["Peer-reviewed biomedical literature (PubMed, Nature Medicine)", "Pharmacology reviews", "Biochemical science journals"]
        },
        {
            "id": "clinical_efficacy_pharmacokinetics",
            "name": "Clinical Trial Efficacy & Pharmacokinetics",
            "focus": "Phase 1-3 clinical trial endpoints, randomized controlled trial (RCT) results, bioavailability, half-life, dosing regimens, and primary/secondary efficacy outcomes for {topic}.",
            "search_queries": [
                '"{topic}" Phase 3 clinical trial RCT results primary endpoints',
                '"{topic}" pharmacokinetics bioavailability half-life clearance dosing'
            ],
            "primary_source_types": ["ClinicalTrials.gov registry", "New England Journal of Medicine / The Lancet", "FDA drug review packages"]
        },
        {
            "id": "safety_adverse_events",
            "name": "Safety Profile, Adverse Events & Contraindications",
            "focus": "Incidence of adverse drug reactions, boxed warnings, tolerability profiles, long-term safety surveillance, drug-drug interactions, and contraindications in {topic}.",
            "search_queries": [
                '"{topic}" adverse events incidence boxed warnings contraindications',
                '"{topic}" long term safety tolerability post market surveillance'
            ],
            "primary_source_types": ["FDA MedWatch adverse event reports", "EMA pharmacovigilance bulletins", "Independent safety meta-analyses"]
        },
        {
            "id": "regulatory_patent_landscape",
            "name": "Regulatory Milestones, Patent Landscape & Generic Timelines",
            "focus": "FDA/EMA approval timelines, priority review designations, patent exclusivity expiries, Orange Book listings, and biosimilar/generic development for {topic}.",
            "search_queries": [
                '"{topic}" FDA EMA approval history Orange Book patent expiration',
                '"{topic}" biosimilar generic entry timeline regulatory exclusivity'
            ],
            "primary_source_types": ["FDA Orange Book", "EMA European Public Assessment Reports (EPAR)", "Patent office filings (USPTO/EPO)"]
        },
        {
            "id": "pricing_market_access",
            "name": "Pricing, Insurance Reimbursement & Market Access",
            "focus": "List price vs net price, insurance coverage criteria, prior authorization hurdles, Medicare/Medicaid reimbursement, and global health economics/cost-effectiveness for {topic}.",
            "search_queries": [
                '"{topic}" list price net cost insurance coverage prior authorization',
                '"{topic}" ICER cost effectiveness health technology assessment'
            ],
            "primary_source_types": ["ICER value assessment reports", "Formulary placement guides", "Health economics and outcomes research (HEOR)"]
        },
        {
            "id": "real_world_evidence",
            "name": "Real-World Evidence & Emerging Secondary Indications",
            "focus": "Observational real-world evidence, off-label usage patterns, pipeline expansion trials for secondary indications, and next-generation combination therapies in {topic}.",
            "search_queries": [
                '"{topic}" real world evidence patient registry observational studies',
                '"{topic}" pipeline expansion secondary indications clinical trials'
            ],
            "primary_source_types": ["Real-world patient registries", "Medical congress abstracts (ADA, EASD, ASCO)", "Investigational pipeline trackers"]
        },
    ],

    "geopolitical_macro": [
        {
            "id": "strategic_geography_trade",
            "name": "Strategic Geography, Trade Volumes & Economic Significance",
            "focus": "Chokepoint topography, annual maritime trade volume, cargo throughput, critical commodity dependencies (energy, microchips), and transit statistics for {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" maritime trade volume annual cargo transit statistics',
                '"{topic}" strategic chokepoint global GDP commodity flow dependency'
            ],
            "primary_source_types": ["Maritime AIS tracking databases", "UNCTAD maritime transport reports", "Chamber of Shipping trade assessments"]
        },
        {
            "id": "historical_legal_claims",
            "name": "Historical Treaties, Sovereignty Claims & Legal Status",
            "focus": "Sovereignty declarations, statutory baselines, international law of the sea (UNCLOS), treaty commitments, and disputed jurisdictional status regarding {topic}.",
            "search_queries": [
                '"{topic}" sovereignty claims international law UNCLOS legal status',
                '"{topic}" historical treaties diplomatic agreements territorial baselines'
            ],
            "primary_source_types": ["UNCLOS legal texts and tribunal awards", "Bilateral treaties and joint communiques", "International law reviews"]
        },
        {
            "id": "military_force_posture",
            "name": "Military Force Posture, Defense Capabilities & Deterrence",
            "focus": "Force projection capabilities, naval/aerial presence, missile defense envelopes, anti-access/area denial (A2/AD) assets, and readiness assessments surrounding {topic}.",
            "search_queries": [
                '"{topic}" military force posture naval presence deterrence capability',
                '"{topic}" anti-access area denial A2AD missile coverage readiness'
            ],
            "primary_source_types": ["IISS Military Balance reports", "CSIS / RAND defense assessments", "Ministry of Defense annual white papers"]
        },
        {
            "id": "economic_supply_vulnerability",
            "name": "Economic Disruption, Supply Chain Shocks & Global Cascades",
            "focus": "Re-routing costs, insurance freight premiums, supply chain delay estimates, global macroeconomic loss projections, and alternative transport corridors for {topic}.",
            "search_queries": [
                '"{topic}" supply chain disruption insurance freight premiums economic cost',
                '"{topic}" shipping reroute delay costs global GDP impact simulation'
            ],
            "primary_source_types": ["IMF / World Bank macroeconomic models", "Lloyd's of London maritime insurance reports", "Global supply chain logistics indices"]
        },
        {
            "id": "diplomatic_coalitions",
            "name": "Diplomatic Alignments, Bilateral Positions & Multilateral Coalitions",
            "focus": "Major power stances (US, EU, regional allies), bilateral security treaties, diplomatic deterrence messaging, and coalition alignment regarding {topic}.",
            "search_queries": [
                '"{topic}" diplomatic alignment international coalition statements',
                '"{topic}" bilateral security treaties foreign ministry communiques'
            ],
            "primary_source_types": ["Official foreign ministry transcripts", "Congressional Research Service (CRS) reports", "Diplomatic policy think tanks (Brookings, Chatham House)"]
        },
        {
            "id": "escalation_crisis_scenarios",
            "name": "Escalation Scenarios, Risk Thresholds & De-escalation Levers",
            "focus": "Gray-zone coercion measures, quarantine/blockade operational mechanics, threshold triggers for conflict, crisis communication channels, and de-escalation mechanisms for {topic}.",
            "search_queries": [
                '"{topic}" gray zone coercion blockade scenarios escalation pathways',
                '"{topic}" conflict risk thresholds de-escalation hotlines off-ramps'
            ],
            "primary_source_types": ["Crisis simulation / wargame white papers", "Strategic studies institute monographs", "Conflict monitoring intelligence bulletins"]
        },
    ],

    "consumer_hardware": [
        {
            "id": "hardware_architecture_specs",
            "name": "Hardware Architecture & Technical Specifications",
            "focus": "Silicon architecture, component specs, display/sensor technologies, chassis thermal design, connectivity standards, and interface specs for {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" technical specifications hardware teardown silicon',
                '"{topic}" processor display memory configuration specs architecture'
            ],
            "primary_source_types": ["Official hardware whitepapers", "Detailed engineering spec sheets", "AnandTech / Tom's Hardware technical analyses"]
        },
        {
            "id": "benchmarks_battery_thermals",
            "name": "Empirical Benchmarks, Battery Endurance & Performance",
            "focus": "Standardized synthetic benchmarks, sustained real-world workloads, battery runtimes, thermal throttling thresholds, and acoustic noise levels for {topic}.",
            "search_queries": [
                '"{topic}" benchmark results Geekbench Cinebench battery life test',
                '"{topic}" real world performance sustained load thermal throttling'
            ],
            "primary_source_types": ["Independent laboratory reviews (RTings, Notebookcheck)", "Standardized benchmark databases", "Direct head-to-head comparison tests"]
        },
        {
            "id": "build_teardown_repairability",
            "name": "Build Quality, Materials, Teardown & Repairability",
            "focus": "Chassis durability, structural integrity, hinge/port stress tolerance, internal modularity, iFixit repairability scores, and spare parts availability for {topic}.",
            "search_queries": [
                '"{topic}" teardown iFixit repairability score build materials',
                '"{topic}" durability drop test chassis internal modularity'
            ],
            "primary_source_types": ["iFixit teardowns", "Hardware durability lab tests", "Authorized service manuals"]
        },
        {
            "id": "software_ecosystem_support",
            "name": "Software Integration, OS Support & Long-Term Updates",
            "focus": "Operating system stability, firmware reliability, proprietary feature integrations, platform ecosystem lock-in, and guaranteed software support lifetime for {topic}.",
            "search_queries": [
                '"{topic}" OS software support update policy lifespan firmware',
                '"{topic}" software ecosystem integration compatibility issues'
            ],
            "primary_source_types": ["Manufacturer support lifecycle documentation", "OS release changelogs", "Developer forum hardware reports"]
        },
        {
            "id": "user_sentiment_reliability",
            "name": "User Sentiment, Reliability Records & Recurring Defects",
            "focus": "Long-term owner retrospectives (3-12 months), recurring hardware flaws, coil whine, display panel lotteries, customer service RMA experiences, and forum complaints for {topic}.",
            "search_queries": [
                '"{topic}" common issues known defects reddit long term review',
                '"{topic}" customer complaints reliability problems RMA quality control'
            ],
            "primary_source_types": ["Reddit enthusiast communities (r/hardware, device subs)", "Consumer complaint registries", "Long-term retrospective reviews"]
        },
        {
            "id": "pricing_buying_verdict",
            "name": "Pricing, Total Value Proposition & Buying Recommendations",
            "focus": "Retail pricing tiers, sales discounting cycles, cost-per-performance ratio, depreciation curves, and tailored recommendations by user persona for {topic}.",
            "search_queries": [
                '"{topic}" price value proposition buying verdict review',
                '"{topic}" configurations price comparison who should buy recommendation'
            ],
            "primary_source_types": ["Authoritative editorial buying guides (The Verge, Wirecutter)", "Price history trackers (CamelCamelCamel)", "Long-range value retention analyses"]
        },
    ],

    "business_finance": [
        {
            "id": "business_model_unit_economics",
            "name": "Business Model, Revenue Streams & Unit Economics",
            "focus": "Core monetization mechanisms, customer acquisition cost (CAC), lifetime value (LTV), revenue breakdown by segment/geography, and contract structures for {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" business model revenue streams segment breakdown',
                '"{topic}" unit economics CAC LTV monetization strategy'
            ],
            "primary_source_types": ["Form 10-K / 10-Q Item 1 and Item 7", "S-1 registration statements", "Investor day presentations"]
        },
        {
            "id": "financial_performance_valuation",
            "name": "Financial Performance, Margins & Valuation Multiples",
            "focus": "Multi-year historical revenue growth, gross/operating/EBITDA margins, free cash flow conversion, balance sheet liquidity, debt structure, and valuation multiples (P/E, EV/Sales, EV/EBITDA) for {topic}.",
            "search_queries": [
                '"{topic}" financial results quarterly earnings revenue growth margins',
                '"{topic}" valuation multiples PE EV EBITDA free cash flow balance sheet'
            ],
            "primary_source_types": ["SEC EDGAR filings", "Bloomberg / Yahoo Finance financial summaries", "Quarterly earnings press releases"]
        },
        {
            "id": "competitive_moat_market_share",
            "name": "Competitive Moat, Market Share & Defensibility",
            "focus": "Product portfolio, market share breakdown, customer retention (NRR), switching costs, network effects, intellectual property, and structural defensibility for {topic}.",
            "search_queries": [
                '"{topic}" market share competitive moat defensibility NRR',
                '"{topic}" competitive landscape barriers to entry customer retention'
            ],
            "primary_source_types": ["Market intelligence reports (Gartner, IDC)", "Form 10-K competitor disclosures", "Industry moat analyses"]
        },
        {
            "id": "leadership_capital_allocation",
            "name": "Leadership, Governance & Capital Allocation",
            "focus": "Executive leadership track record, board composition, capital allocation strategy (dividends, buybacks, capex), M&A history, and corporate governance for {topic}.",
            "search_queries": [
                '"{topic}" capital allocation strategy buybacks dividends capex MA',
                '"{topic}" executive leadership track record board governance'
            ],
            "primary_source_types": ["Proxy statements (DEF 14A)", "CEO shareholder annual letters", "Corporate governance scorecards"]
        },
        {
            "id": "risks_regulatory_exposure",
            "name": "Risk Factors, Regulatory Scrutiny & Controversies",
            "focus": "Active litigation, regulatory investigations, customer concentration, key-person risk, supply chain dependencies, governance red flags, and short-seller allegations facing {topic}.",
            "search_queries": [
                '"{topic}" risk factors litigation regulatory investigation 10-K',
                '"{topic}" controversies vulnerabilities customer concentration'
            ],
            "primary_source_types": ["Form 10-K Item 1A (Risk Factors)", "Court dockets and legal filings", "Investigative financial reports"]
        },
        {
            "id": "forward_guidance_catalysts",
            "name": "Forward Guidance, Growth Catalysts & Analyst Consensus",
            "focus": "Management forward guidance, Wall Street consensus earnings/revenue forecasts, upcoming product catalysts, addressable market expansion, and near-term milestones for {topic}.",
            "search_queries": [
                '"{topic}" forward guidance earnings consensus analyst estimates',
                '"{topic}" growth catalysts upcoming milestones product roadmap'
            ],
            "primary_source_types": ["Earnings call Q&A transcripts", "Sell-side consensus estimate revisions", "Corporate milestone calendars"]
        },
    ],

    "policy_legal": [
        {
            "id": "legislative_genesis",
            "name": "Legislative Genesis, Statutory Authority & Jurisdiction",
            "focus": "Origins of the policy/statute, enabling legislation, constitutional/statutory authority, jurisdictional reach, and legislative intent of {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" legislative history statutory authority enabling act',
                '"{topic}" jurisdictional scope enabling legislation legislative intent'
            ],
            "primary_source_types": ["Official sovereign gazettes", "Congressional committee reports", "Official legal registers (EUR-Lex, Federal Register)"]
        },
        {
            "id": "compliance_obligations",
            "name": "Core Compliance Obligations & Operational Mandates",
            "focus": "Specific legal mandates, auditing requirements, operational constraints, technical controls, certifications, and reporting protocols imposed by {topic}.",
            "search_queries": [
                '"{topic}" compliance obligations mandatory standards requirements',
                '"{topic}" operational constraints reporting protocols auditing checklist'
            ],
            "primary_source_types": ["Administrative rulebooks", "Standard operating procedures", "Official compliance checklists"]
        },
        {
            "id": "enforcement_penalties",
            "name": "Enforcement Mechanisms, Supervisory Bodies & Sanctions",
            "focus": "Enforcement agencies, investigative authorities, audit powers, civil/criminal sanctions, statutory fine tiers, and historical enforcement precedents under {topic}.",
            "search_queries": [
                '"{topic}" enforcement penalties fines sanctions regulatory body',
                '"{topic}" investigative powers audit enforcement actions precedents'
            ],
            "primary_source_types": ["Agency enforcement bulletins", "Regulatory consent decrees", "Penalty calculation guidelines"]
        },
        {
            "id": "stakeholder_economic_impact",
            "name": "Stakeholder Impact, Economic Friction & Industry Debate",
            "focus": "Compliance costs across business tiers, industry lobbying stances, civil society viewpoints, economic friction, and legal challenges regarding {topic}.",
            "search_queries": [
                '"{topic}" economic impact compliance costs industry reaction',
                '"{topic}" stakeholder debate lobbying legal challenges'
            ],
            "primary_source_types": ["Public comment filings", "Industry trade association whitepapers", "Economic impact assessments"]
        },
        {
            "id": "implementation_roadmap",
            "name": "Implementation Roadmap, Timelines & Safe Harbors",
            "focus": "Statutory effective dates, phased implementation timetables, grace periods, safe harbor provisions, grandfathering rules, and critical milestones for {topic}.",
            "search_queries": [
                '"{topic}" implementation timeline effective dates grace period',
                '"{topic}" compliance deadlines safe harbor grandfathering'
            ],
            "primary_source_types": ["Regulator implementation guidance memos", "Legal advisory bulletins", "Readiness surveys"]
        },
        {
            "id": "cross_border_alignment",
            "name": "Cross-Border Harmonization & International Precedents",
            "focus": "Extraterritorial reach, international treaty obligations, comparative cross-border regulations (US, EU, UK, APAC), and global harmonization hurdles for {topic}.",
            "search_queries": [
                '"{topic}" extraterritorial reach international alignment comparative law',
                '"{topic}" cross border regulation treaty harmonization precedents'
            ],
            "primary_source_types": ["Comparative law reviews", "International regulatory cooperation reports", "Cross-border legal trackers"]
        },
    ],

    "technology_architecture": [
        {
            "id": "architecture_protocols",
            "name": "Technical Foundations, Protocols & State Architecture",
            "focus": "Underlying architectural mechanisms, protocols, state management models, core algorithms, data flow, and technical specifications of {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" architecture protocol state machine specifications',
                '"{topic}" internal design algorithms data structures implementation'
            ],
            "primary_source_types": ["Engineering whitepapers", "System architecture RFCs", "Core open-source source code repositories"]
        },
        {
            "id": "empirical_benchmarks",
            "name": "Empirical Benchmarks, Throughput & Latency Scaling",
            "focus": "Quantitative benchmark figures, p50/p99 latency distributions, throughput scaling, memory footprint, resource utilization, and stress-test data for {topic}.",
            "search_queries": [
                '"{topic}" benchmark results latency throughput p99 scaling',
                '"{topic}" performance evaluation stress test hardware utilization'
            ],
            "primary_source_types": ["Published benchmark testbeds", "Peer-reviewed USENIX/ACM papers", "Technical engineering blog performance posts"]
        },
        {
            "id": "operational_tradeoffs",
            "name": "Operational Trade-offs, Scalability & System Constraints",
            "focus": "CAP theorem trade-offs, consistency guarantees, concurrency bottlenecks, operational overhead, maintenance burden, and scaling limits for {topic}.",
            "search_queries": [
                '"{topic}" operational trade-offs concurrency bottlenecks scaling limits',
                '"{topic}" consistency models CAP theorem failure modes overhead'
            ],
            "primary_source_types": ["Production incident post-mortems", "High-scale engineering case studies", "System reliability evaluations"]
        },
        {
            "id": "ecosystem_tooling",
            "name": "Ecosystem Maturity, Developer Tooling & Integrations",
            "focus": "SDK and library support, developer tooling ecosystem, debugging/observability tools, CI/CD integrations, and community maturity for {topic}.",
            "search_queries": [
                '"{topic}" developer tooling SDK libraries ecosystem integration',
                '"{topic}" observability debugging monitoring toolchain support'
            ],
            "primary_source_types": ["Package registries (npm, PyPI, crates.io)", "Developer documentation portals", "Ecosystem survey reports"]
        },
        {
            "id": "security_threat_model",
            "name": "Security Threat Model, Attack Surfaces & Failure Recovery",
            "focus": "Known vulnerabilities (CVEs), threat vectors, authentication/authorization schemes, failure recovery, split-brain scenarios, and disaster mitigation for {topic}.",
            "search_queries": [
                '"{topic}" security vulnerabilities threat model CVE attack surface',
                '"{topic}" failure recovery disaster mitigation split-brain scenarios'
            ],
            "primary_source_types": ["Security audit reports", "CVE databases", "Threat modeling whitepapers"]
        },
        {
            "id": "strategic_evolution",
            "name": "Strategic Technical Evolution & Next-Order Standards",
            "focus": "12-24 month technical roadmap, upcoming RFCs/proposals, architectural convergence, and emerging alternative paradigms for {topic}.",
            "search_queries": [
                '"{topic}" technical roadmap future RFC standards evolution',
                '"{topic}" emerging paradigms architectural convergence trends'
            ],
            "primary_source_types": ["Working group drafts", "Technical keynote presentations", "Maintainer visionary roadmaps"]
        },
    ],

    "lifestyle_travel_general": [
        {
            "id": "overview_context",
            "name": "Comprehensive Overview, Context & Background",
            "focus": "Essential introduction, geographic/cultural context, historical background, key highlights, and primary reasons to engage with {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" overview historical background cultural significance',
                '"{topic}" introduction essential highlights context'
            ],
            "primary_source_types": ["Official tourism portals", "Reputable cultural encyclopedias", "Expert destination guides"]
        },
        {
            "id": "cost_logistics",
            "name": "Cost Estimates, Budgeting, Transportation & Logistics",
            "focus": "Detailed cost estimates across budget levels (budget, mid-range, luxury), transit options, passes, accommodation rates, and logistical planning for {topic}.",
            "search_queries": [
                '"{topic}" cost breakdown travel budget transit passes accommodation',
                '"{topic}" transportation logistics travel expenses estimates'
            ],
            "primary_source_types": ["Transit authority fare tables", "Cost-of-living databases (Numbeo)", "Travel expense aggregators"]
        },
        {
            "id": "top_recommendations",
            "name": "Top Recommendations, Curated Itineraries & Options",
            "focus": "Curated day-by-day itineraries, must-see highlights, off-the-beaten-path recommendations, and comparative activity options for {topic}.",
            "search_queries": [
                '"{topic}" curated itinerary day by day must see attractions',
                '"{topic}" top recommendations hidden gems activity options'
            ],
            "primary_source_types": ["Leading travel guides (Lonely Planet, Rick Steves)", "Curated editorial destination guides", "Local tourism itineraries"]
        },
        {
            "id": "local_nuances_tips",
            "name": "Local Nuances, Cultural Customs, Etiquette & Insider Tips",
            "focus": "Cultural etiquette, tipping practices, dining customs, language essentials, dress codes, payment preferences (cash vs card), and insider practical tips for {topic}.",
            "search_queries": [
                '"{topic}" cultural etiquette tipping customs insider tips',
                '"{topic}" dining customs payment methods practical advice'
            ],
            "primary_source_types": ["Expat and resident advice blogs", "Cultural etiquette handbooks", "Regional traveler forums"]
        },
        {
            "id": "pitfalls_safety",
            "name": "Common Pitfalls, Safety Warnings, Traps & Alternatives",
            "focus": "Common tourist traps, scams, safety concerns, transit disruptions, overcrowded bottlenecks, and superior alternative destinations or methods for {topic}.",
            "search_queries": [
                '"{topic}" common scams tourist traps safety warnings what to avoid',
                '"{topic}" overcrowding bottlenecks better alternatives recommendations'
            ],
            "primary_source_types": ["Consular travel advisories", "Traveler safety warning reports", "Alternative destination studies"]
        },
        {
            "id": "seasonality_timing",
            "name": "Seasonal Considerations, Timing, Weather & Booking Strategy",
            "focus": "Optimal seasons to visit, weather patterns, peak vs shoulder vs off-peak timing, local festival dates, crowd calendars, and advance booking windows for {topic}.",
            "search_queries": [
                '"{topic}" best time to visit weather crowd calendar booking window',
                '"{topic}" peak vs shoulder season festival dates seasonal timing'
            ],
            "primary_source_types": ["Historical weather archives", "Crowd calendar indices", "Ticket booking release schedules"]
        },
    ],

    "universal_inquiry": [
        {
            "id": "foundational_principles",
            "name": "Foundational Principles, Physics/Mechanisms & Origins",
            "focus": "Fundamental operating principles, underlying physical/structural mechanisms, historical development, and core taxonomies of {topic}. Scope: {scope}",
            "search_queries": [
                '"{topic}" fundamental operating principles underlying mechanisms',
                '"{topic}" scientific foundations core mechanisms history'
            ],
            "primary_source_types": ["Academic textbooks", "Peer-reviewed foundational literature", "Subject matter reference handbooks"]
        },
        {
            "id": "structural_composition",
            "name": "Material Composition, Structural Design & Methodology",
            "focus": "Core materials, constituent components, architectural/structural design, fabrication techniques, and physical properties for {topic}.",
            "search_queries": [
                '"{topic}" material composition structural design specifications',
                '"{topic}" components fabrication physical properties methodology'
            ],
            "primary_source_types": ["Technical data sheets", "Material science databases", "Engineering design standards"]
        },
        {
            "id": "empirical_benchmarks",
            "name": "Empirical Measurements, Performance Benchmarks & Efficacy",
            "focus": "Standardized test metrics, quantifiable performance data, empirical measurement methods, comparative benchmarks, and efficiency ratings for {topic}.",
            "search_queries": [
                '"{topic}" standardized test results empirical measurements performance',
                '"{topic}" laboratory benchmark ratings efficiency metrics'
            ],
            "primary_source_types": ["Standardized testing laboratory reports (ASTM, ISO, etc.)", "Comparative empirical research papers", "Independent testing databases"]
        },
        {
            "id": "economic_practical_factors",
            "name": "Economic Factors, Cost Dynamics & Practical Implementation",
            "focus": "Cost structures, resource availability, installation/adoption overhead, maintenance lifecycles, and operational economics for {topic}.",
            "search_queries": [
                '"{topic}" cost structure economics installation expenses lifecycle',
                '"{topic}" resource availability adoption overhead operational cost'
            ],
            "primary_source_types": ["Industry cost indexes", "Economic feasibility studies", "Professional practice guidelines"]
        },
        {
            "id": "vulnerabilities_controversies",
            "name": "Known Vulnerabilities, Failure Modes & Key Controversies",
            "focus": "Degradation factors, structural vulnerabilities, disputed scientific/expert claims, safety trade-offs, and critical failure modes in {topic}.",
            "search_queries": [
                '"{topic}" failure modes common defects durability limits degradation',
                '"{topic}" disputed claims safety controversies trade-offs'
            ],
            "primary_source_types": ["Failure analysis case studies", "Safety regulatory notices", "Critical peer review commentaries"]
        },
        {
            "id": "future_trajectory",
            "name": "Emerging Innovations, Next-Order Trends & Expert Consensus",
            "focus": "Next-generation developments, breakthrough methods, standardization trajectories, and leading expert consensus shaping {topic}.",
            "search_queries": [
                '"{topic}" future developments emerging innovations next generation',
                '"{topic}" expert consensus research roadmap next order trends'
            ],
            "primary_source_types": ["Future research agendas", "Keynote conference proceedings", "Delphi consensus panels"]
        },
    ],
}


def detect_domain(topic: str, scope: str = "") -> str:
    """
    Analyzes keywords, syntax, and user intent across topic and scope
    to select the best matching research domain category.
    Returns one of SUPPORTED_DOMAINS (defaulting to 'universal_inquiry').
    """
    topic_str = str(topic or "").strip()
    scope_str = str(scope or "").strip()

    if not topic_str and not scope_str:
        return "universal_inquiry"

    combined_topic = topic_str.lower()
    combined_scope = scope_str.lower()

    scores: Dict[str, int] = {domain: 0 for domain in SUPPORTED_DOMAINS}

    for domain, patterns in DOMAIN_PATTERNS.items():
        for pattern, weight in patterns:
            topic_matches = len(re.findall(pattern, combined_topic))
            if topic_matches > 0:
                scores[domain] += topic_matches * weight * 2

            if combined_scope:
                scope_matches = len(re.findall(pattern, combined_scope))
                if scope_matches > 0:
                    scores[domain] += scope_matches * weight

    best_domain = max(scores, key=lambda d: scores[d])
    if scores[best_domain] > 0:
        return best_domain

    return "universal_inquiry"


def generate_fallback_vectors(
    topic: str,
    scope: str = "",
    domain: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Resilient offline vector planner for unit tests and non-LLM execution.
    Selects domain-native inquiry dimensions without cross-domain semantic drift
    or inappropriate software engineering jargon.
    """
    clean_topic = str(topic or "").strip() or "Emerging Research Topic"
    clean_scope = str(scope or "").strip() or "Comprehensive in-depth investigation"

    raw_domain = domain or detect_domain(clean_topic, clean_scope)
    # Resolve any legacy aliases
    target_domain = DOMAIN_ALIASES.get(raw_domain, raw_domain)
    if target_domain not in OFFLINE_VECTOR_TEMPLATES:
        target_domain = "universal_inquiry"

    templates = OFFLINE_VECTOR_TEMPLATES[target_domain]

    vectors: List[Dict[str, Any]] = []
    for t in templates:
        rendered_focus = t["focus"].format(topic=clean_topic, scope=clean_scope)
        rendered_queries = [q.format(topic=clean_topic) for q in t["search_queries"]]
        vectors.append({
            "id": t["id"],
            "name": t["name"],
            "focus": rendered_focus,
            "search_queries": rendered_queries,
            "primary_source_types": list(t["primary_source_types"]),
            "domain": target_domain,
        })

    return vectors


# Backward compatibility alias
generate_vectors_for_topic = generate_fallback_vectors


def get_domain_info(domain: str) -> Dict[str, str]:
    """
    Returns metadata (name, description) for a given domain key.
    """
    resolved = DOMAIN_ALIASES.get(domain, domain)
    return DOMAIN_METADATA.get(resolved, {
        "name": resolved,
        "description": "General research inquiry domain."
    })


if __name__ == "__main__":
    test_topics = [
        ("Authentic Neapolitan Pizza Fermentation and Crust Chemistry", "Wood-fired oven heat dynamics and hydration"),
        ("GLP-1 Receptor Agonists for Obesity: Semaglutide vs Tirzepatide", "Clinical trial endpoints, adverse events, and pricing"),
        ("Taiwan Strait Maritime Shipping Traffic and Blockade Vulnerabilities", "Trade flows, military deterrence, and supply chain shocks"),
        ("MacBook Pro M3 Max vs ThinkPad P1 Gen 6", "Benchmarks, battery endurance, and developer experience"),
        ("Acoustic Panels for Home Studio Soundproofing: Fiberglass vs Rockwool", "NRC absorption coefficients and fire safety"),
    ]

    print("=== Deep Research Adaptive Vectors & Fallback Planner ===")
    for q_topic, q_scope in test_topics:
        dom = detect_domain(q_topic, q_scope)
        vecs = generate_fallback_vectors(q_topic, q_scope, domain=dom)
        valid, errs = validate_vectors(vecs)
        print(f"\n[Topic]: {q_topic}")
        print(f" -> Detected Domain: {dom} ({get_domain_info(dom)['name']})")
        print(f" -> Vectors Valid: {valid} (Errors: {errs})")
        for v in vecs:
            print(f"    * [{v['id']}] {v['name']}")
            print(f"      Queries: {v['search_queries']}")
            print(f"      Sources: {v['primary_source_types']}")
