#!/usr/bin/env python3
"""
Autonomous Multi-Agent Deep Research & Query Fan-Out Planner
Inspired by Gemini Deep Research & Stanford STORM architectures.

Generates structured multi-phase research plans, high-precision query fan-outs (15-25+ queries)
with exact search operators, and recursive gap-analysis heuristics for consumer product research.
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# -----------------------------------------------------------------------------
# Category Knowledge Bases & Domain Archetypes
# -----------------------------------------------------------------------------

CATEGORY_PROFILES: Dict[str, Dict[str, Any]] = {
    "smartphones": {
        "display_name": "Smartphones & Mobile Devices",
        "subreddits": ["r/Android", "r/PickAnAndroidForMe", "r/smartphones", "r/apple"],
        "lab_metrics": [
            "Display peak lux/nits (100% APL vs HDR)",
            "Color accuracy Delta-E & PWM dimming frequency (Hz)",
            "Sustained thermal throttling (3DMark Wild Life Extreme / CPU Throttling Test)",
            "SoC efficiency curves (Geekerwan / Golden Reviewer power draw)",
            "Acoustic loudness & speaker frequency separation (dB SPL)",
            "Battery active use runtime (GSMArena normalized test)",
        ],
        "benchmark_sources": [
            "site:notebookcheck.net",
            "site:gsmarena.com",
            "site:geekerwan.com",
            "site:dxomark.com",
            "site:anandtech.com",
        ],
        "known_failure_modes": [
            "motherboard dead boot / solder fatigue",
            "vertical green line on AMOLED display after OTA update",
            "battery degradation / rapid swelling",
            "camera sensor condensation / OIS lens rattle",
            "thermal throttling in heavy gaming",
        ],
        "required_dimensions": [
            {"id": "pricing_landing", "label": "Net Landing Price & Bank Offers", "priority": "critical"},
            {"id": "performance_sustained", "label": "Sustained Performance & Thermal Stability", "priority": "critical"},
            {"id": "display_lab", "label": "Display Lux, Color Accuracy & PWM Dimming", "priority": "high"},
            {"id": "camera_real_world", "label": "Camera Sensor Specs, Low-Light & OIS", "priority": "high"},
            {"id": "battery_charging", "label": "Battery Life & Charge Degradation Cycle", "priority": "high"},
            {"id": "defect_rate", "label": "Long-Term Defect Rate & Hardware Failures", "priority": "critical"},
            {"id": "local_service_tat", "label": "Authorized Service Network & Turnaround Time", "priority": "critical"},
            {"id": "software_policy", "label": "OS Update Lifecycle & Post-Update Regressions", "priority": "medium"},
        ],
    },
    "laptops": {
        "display_name": "Laptops & Portable Workstations",
        "subreddits": ["r/laptops", "r/SuggestALaptop", "r/pcmasterrace", "r/framework"],
        "lab_metrics": [
            "Display brightness (nits/lux), sRGB / DCI-P3 coverage %, Delta-E",
            "Cinebench R23 30-min loop sustained wattage vs peak PL2/PL1",
            "Surface keyboard deck temperatures under sustained load (°C)",
            "Fan acoustics dB(A) at idle vs full load",
            "Battery runtime in standardized web browsing loop",
            "DPC audio latency (NotebookCheck latency mon)",
        ],
        "benchmark_sources": [
            "site:notebookcheck.net",
            "site:ultrabookreview.com",
            "site:rtings.com",
            "site:tomshardware.com",
            "site:geekerwan.com",
        ],
        "known_failure_modes": [
            "hinge cracking / chassis separation",
            "liquid metal pump-out / thermal degradation",
            "flexgate display cable fatigue",
            "soldered RAM limitations / unrepairable SSD",
            "motherboard VRM overheating",
        ],
        "required_dimensions": [
            {"id": "pricing_landing", "label": "Net Landing Price & RAM/SSD SKU Verification", "priority": "critical"},
            {"id": "thermals_sustained", "label": "Sustained Wattage, Thermals & Fan Noise dB", "priority": "critical"},
            {"id": "display_lab", "label": "Panel Brightness (Nits), Color Space & Response Time", "priority": "high"},
            {"id": "build_repairability", "label": "Hinge Durability, Chassis Materials & Teardown", "priority": "high"},
            {"id": "battery_runtime", "label": "Real-World Normalized Battery Runtime", "priority": "high"},
            {"id": "defect_rate", "label": "Long-Term Defects & Community Sentiment", "priority": "critical"},
            {"id": "warranty_service_tat", "label": "On-Site Warranty Reach & Repair Turnaround", "priority": "critical"},
        ],
    },
    "inverter_acs": {
        "display_name": "Inverter Air Conditioners",
        "subreddits": ["r/indianbuyers", "r/HVAC", "r/appliancerepair", "r/HomeImprovement"],
        "lab_metrics": [
            "BEE ISEER efficiency rating / Energy Star SEER",
            "Rated vs maximum cooling capacity (Watts / BTU) at 43°C & 52°C",
            "Outdoor unit (ODU) compressor acoustic noise (dB SPL)",
            "Indoor unit (IDU) silent mode decibels (dB SPL)",
            "Power consumption curve (50% half load vs 100% full load)",
        ],
        "benchmark_sources": [
            "site:beestarlabel.com",
            "site:energystar.gov",
            "site:consumerreports.org",
            "filetype:pdf inurl:specifications",
        ],
        "known_failure_modes": [
            "refrigerant gas leakage at copper-aluminum U-bends",
            "PCB failure due to voltage surges / moisture",
            "condenser coil corrosion in coastal / high-humidity zones",
            "indoor blower motor bearing rattle",
            "delayed installation / poor vacuuming during setup",
        ],
        "required_dimensions": [
            {"id": "iseer_efficiency", "label": "ISEER Rating & Power Consumption Data", "priority": "critical"},
            {"id": "condenser_materials", "label": "100% Copper Coils & Anti-Corrosion (Blue/Gold Fin)", "priority": "critical"},
            {"id": "cooling_ambient_high", "label": "High-Ambient Cooling Derating at 50°C+", "priority": "high"},
            {"id": "acoustic_noise_db", "label": "Indoor (IDU) and Outdoor (ODU) Noise Levels in dB", "priority": "high"},
            {"id": "pcb_warranty_terms", "label": "PCB & Compressor Warranty Fine Print", "priority": "critical"},
            {"id": "service_tat_installation", "label": "Authorized Brand Service Network & Install TAT", "priority": "critical"},
            {"id": "stabilizer_voltage", "label": "Stabilizer-Free Voltage Operating Window", "priority": "high"},
        ],
    },
    "washing_machines": {
        "display_name": "Washing Machines (Front / Top Load)",
        "subreddits": ["r/appliances", "r/appliancerepair", "r/indianbuyers", "r/HomeImprovement"],
        "lab_metrics": [
            "Energy & water consumption per cycle (kWh & litres/kg)",
            "Wash performance index (standardized soil removal test)",
            "Spin speed (RPM) & residual moisture retention percentage",
            "Acoustic noise dB during wash vs high-speed spin cycle",
            "Motor wattage & direct drive vs belt inverter efficiency",
        ],
        "benchmark_sources": [
            "site:consumerreports.org",
            "site:which.co.uk",
            "site:beestarlabel.com",
            "filetype:pdf inurl:manual",
        ],
        "known_failure_modes": [
            "drum spider arm galvanic corrosion",
            "outer tub bearing seal leakage & bearing destruction",
            "suspension damper / shock absorber breakdown & violent shaking",
            "inverter control board moisture damage",
            "drain pump impeller blockage",
        ],
        "required_dimensions": [
            {"id": "motor_drum_architecture", "label": "Direct Drive vs Belt Inverter & Stainless Drum", "priority": "critical"},
            {"id": "water_energy_efficiency", "label": "Water & Electricity Consumption per Cycle", "priority": "high"},
            {"id": "spin_noise_vibration", "label": "Acoustic Noise dB & Vibration Dampening", "priority": "high"},
            {"id": "hard_water_resilience", "label": "Hard Water Softening / Descaling Resistance", "priority": "high"},
            {"id": "spider_bearing_durability", "label": "Tub Bearing & Spider Arm Teardown Durability", "priority": "critical"},
            {"id": "service_tat_spares", "label": "Brand Service Hub Reach & Spare Part Availability", "priority": "critical"},
        ],
    },
    "skincare": {
        "display_name": "Skincare & Dermatological Formulations",
        "subreddits": ["r/SkincareAddiction", "r/IndianSkincareAddicts", "r/AsianBeauty", "r/30PlusSkinCare"],
        "lab_metrics": [
            "Active ingredient concentration (% wt/vol)",
            "Formulation pH range (optimal absorption vs skin barrier stability)",
            "Carrier base, delivery vehicles (liposomes, encapsulation)",
            "Third-party patch test / clinical efficacy publications",
            "Packaging light & air barrier (amber glass, airless vacuum pump)",
        ],
        "benchmark_sources": [
            "site:pubmed.ncbi.nlm.nih.gov",
            "site:incidecoder.com",
            "site:cosdna.com",
            "site:paulaschoice.com",
        ],
        "known_failure_modes": [
            "rapid active oxidation (e.g., Vitamin C turning yellow/brown)",
            "barrier destruction & severe purging vs allergic dermatitis",
            "comedogenic pore clogging from heavy esters/silicones",
            "formula separation / unstable emulsion",
            "counterfeits from unverified e-commerce marketplace sellers",
        ],
        "required_dimensions": [
            {"id": "active_concentration", "label": "Verified Active Ingredient % wt/vol & Purity", "priority": "critical"},
            {"id": "ph_formulation_stability", "label": "pH Level & Encapsulation/Delivery Vehicle", "priority": "high"},
            {"id": "safety_comedogenic", "label": "Irritancy, Non-Comedogenic Status & Fragrance-Free", "priority": "critical"},
            {"id": "packaging_preservation", "label": "Airless / UV Protective Packaging", "priority": "high"},
            {"id": "clinical_evidence", "label": "Independent Peer-Reviewed Clinical Trial Evidence", "priority": "high"},
            {"id": "authorized_channel_counterfeit", "label": "Authorized Distribution Channel & Batch Tracking", "priority": "critical"},
        ],
    },
    "supplements": {
        "display_name": "Dietary Supplements & Nutraceuticals",
        "subreddits": ["r/Supplements", "r/Fitness", "r/gainit", "r/moreplatesmoredates"],
        "lab_metrics": [
            "Verified active purity & true protein % (dry basis)",
            "Absence of amino spiking (glycine/taurine nitrogen inflation)",
            "Heavy metal screening (Lead, Arsenic, Cadmium, Mercury ppm)",
            "Microbial contamination testing (E. coli, Salmonella, mold CFU/g)",
            "Digestibility score (PDCAAS / DIAAS) and digestive enzyme complex",
        ],
        "benchmark_sources": [
            "site:labdoor.com",
            "site:consumerlab.com",
            "site:trustified.in",
            "site:informed-sport.com",
            "site:pubmed.ncbi.nlm.nih.gov",
        ],
        "known_failure_modes": [
            "amino spiking / inflated protein claims",
            "heavy metal contamination exceeding safe daily intake",
            "gastrointestinal distress, bloating, or lactase insufficiency",
            "unauthorized grey-market imports or counterfeit QR seals",
            "banned substance contamination for athletes (WADA list)",
        ],
        "required_dimensions": [
            {"id": "active_purity_potency", "label": "Third-Party Certified Active Purity & Potency", "priority": "critical"},
            {"id": "zero_amino_spiking", "label": "Zero Amino Spiking & Heavy Metals Lab Panel", "priority": "critical"},
            {"id": "lab_transparency_coa", "label": "Batch-Wise Certificate of Analysis (COA) Public Access", "priority": "critical"},
            {"id": "digestibility_tolerance", "label": "Digestibility, Enzyme Inclusion & Gut Tolerance", "priority": "high"},
            {"id": "statutory_licensing", "label": "Statutory Licensing (FSSAI/FDA/GMP Certification)", "priority": "critical"},
            {"id": "authenticity_verification", "label": "Tamper-Proof Verification (Scratch QR / Official Importer)", "priority": "critical"},
        ],
    },
    "tws_audio": {
        "display_name": "True Wireless Stereo (TWS) Earbuds & Audio",
        "subreddits": ["r/headphones", "r/Earbuds", "r/audiophile", "r/inearfidelity"],
        "lab_metrics": [
            "Harman curve target compliance / frequency response curve",
            "Active Noise Cancellation (ANC) decibel attenuation across spectrum (dB)",
            "Microphone signal-to-noise ratio (SNR) in loud ambient environments",
            "Bluetooth latency in milliseconds (ms) with supported codecs",
            "True battery cycle runtime with ANC enabled",
        ],
        "benchmark_sources": [
            "site:rtings.com",
            "site:soundguys.com",
            "site:crinacle.com",
            "site:head-fi.org",
        ],
        "known_failure_modes": [
            "battery capacity collapse after 9-12 months (non-replaceable cell)",
            "ANC crackling / wind noise feedback squeal",
            "case charging pin corrosion / one earbud failing to charge",
            "firmware updates degrading sound signature or volume",
            "insecure fit / driver rattling under heavy bass",
        ],
        "required_dimensions": [
            {"id": "frequency_response_sound", "label": "Harman Target Compliance & Sound Separation", "priority": "critical"},
            {"id": "anc_transparency_lab", "label": "Lab-Measured ANC Attenuation (dB) & Mic Clarity", "priority": "high"},
            {"id": "codec_latency", "label": "Hi-Res Codecs (LDAC/LHDC/aptX) & Latency (ms)", "priority": "high"},
            {"id": "battery_degradation", "label": "Battery Life & Long-Term Cell Longevity", "priority": "critical"},
            {"id": "water_sweat_rating", "label": "IP Rating (IPX4/57) & Case Build Quality", "priority": "medium"},
            {"id": "defect_rate_anc", "label": "Known Defect Patterns & RMA Replacement Policy", "priority": "critical"},
        ],
    },
    "generic": {
        "display_name": "Consumer Product Category",
        "subreddits": ["r/BuyItForLife", "r/consumer", "r/reviews", "r/redditgetsdrawn"],
        "lab_metrics": [
            "Objective physical stress tests & load capacities",
            "Acoustic noise levels & thermal efficiency measurements",
            "Energy / power consumption ratings & statutory test data",
            "Component teardown & material build composition verification",
        ],
        "benchmark_sources": [
            "site:rtings.com",
            "site:consumerreports.org",
            "site:wirecutter.com",
            "filetype:pdf inurl:specifications",
        ],
        "known_failure_modes": [
            "premature structural / component failure",
            "inaccurate marketing performance claims",
            "thermal or power-supply failure under extended load",
            "poor customer service and lack of spare parts",
        ],
        "required_dimensions": [
            {"id": "pricing_landing", "label": "Net Effective Landing Cost & Warranty Coverage", "priority": "critical"},
            {"id": "objective_benchmarks", "label": "Verifiable Lab Benchmark Metrics & Specifications", "priority": "critical"},
            {"id": "build_teardown", "label": "Internal Component Teardown & Material Durability", "priority": "high"},
            {"id": "sentiment_defect_audit", "label": "Unvarnished Long-Term Community Failure Logs", "priority": "critical"},
            {"id": "local_service_statutory", "label": "Regional Statutory Compliance & Authorized Service Hubs", "priority": "critical"},
        ],
    },
}

REGIONAL_REGULATORS: Dict[str, Dict[str, Any]] = {
    "IN": {
        "name": "India",
        "currency": "INR",
        "currency_symbol": "₹",
        "safety_regulators": ["BIS (Bureau of Indian Standards) - CRS registration", "WPC (Wireless Planning & Coordination) for RF"],
        "energy_regulators": ["BEE Star Label (Bureau of Energy Efficiency) / ISEER standard"],
        "health_regulators": ["FSSAI (Food Safety and Standards Authority of India)", "CDSCO for cosmetics/medical"],
        "consumer_forums": "site:reddit.com OR site:consumercomplaints.in",
        "climate_factors": ["High ambient heat (up to 50°C)", "Monsoon high humidity / coastal salt fog", "Grid voltage fluctuations (160V-280V)", "Hard water TDS (>500 ppm)"],
        "key_search_terms": "India OR BIS OR BEE OR \"authorized service center\" OR \"spare parts\" OR INR OR ₹",
    },
    "US": {
        "name": "United States",
        "currency": "USD",
        "currency_symbol": "$",
        "safety_regulators": ["FCC (Federal Communications Commission) Part 15", "UL (Underwriters Laboratories) / ETL Listed"],
        "energy_regulators": ["EPA Energy Star / DOE Efficiency Standards"],
        "health_regulators": ["FDA (Food and Drug Administration) cGMP", "FTC consumer truth-in-advertising"],
        "consumer_forums": "site:reddit.com OR site:bbb.org OR site:trustpilot.com",
        "climate_factors": ["120V 60Hz electrical grid", "Extreme winter freezing / summer humidity variation"],
        "key_search_terms": "USA OR FCC OR \"Energy Star\" OR UL OR \"warranty repair\" OR USD OR $",
    },
    "EU": {
        "name": "European Union",
        "currency": "EUR",
        "currency_symbol": "€",
        "safety_regulators": ["CE Marking (Conformité Européenne)", "RoHS (Restriction of Hazardous Substances) Directive"],
        "energy_regulators": ["EU Energy Label (A to G Scale)", "ErP (Energy-related Products) Ecodesign"],
        "health_regulators": ["EU Cosmetics Regulation (EC) No 1223/2009", "EFSA (European Food Safety Authority)"],
        "consumer_forums": "site:reddit.com OR site:trustpilot.com",
        "climate_factors": ["230V 50Hz grid", "EU Right to Repair Directive (10-year spare parts availability)"],
        "key_search_terms": "Europe OR EU OR CE OR \"Right to Repair\" OR \"Energy Label\" OR EUR OR €",
    },
    "UK": {
        "name": "United Kingdom",
        "currency": "GBP",
        "currency_symbol": "£",
        "safety_regulators": ["UKCA (UK Conformity Assessed)"],
        "energy_regulators": ["UK Energy Label Framework"],
        "health_regulators": ["MHRA / UK Cosmetics Regulation"],
        "consumer_forums": "site:reddit.com OR site:which.co.uk OR site:trustpilot.com",
        "climate_factors": ["230V 50Hz grid", "Consumer Rights Act 2015"],
        "key_search_terms": "UK OR UKCA OR Which OR \"authorized repair\" OR GBP OR £",
    },
}

# -----------------------------------------------------------------------------
# Research Planner Class
# -----------------------------------------------------------------------------

class ResearchPlanner:
    """
    Generates structured multi-phase research plans, high-density search queries,
    and recursive gap-analysis heuristics for consumer product research.
    """

    def __init__(self, category: str, region: str = "IN", confidence_threshold: float = 0.70):
        self.category = category.lower().strip().replace("-", "_").replace(" ", "_")
        self.region_code = region.upper().strip()
        self.confidence_threshold = confidence_threshold

        # Resolve category profile or fallback to generic
        self.profile = CATEGORY_PROFILES.get(self.category, CATEGORY_PROFILES["generic"])
        # Resolve regional regulator or fallback to IN
        self.regional_info = REGIONAL_REGULATORS.get(self.region_code, REGIONAL_REGULATORS["IN"])

    def parse_candidates(self, candidates_input: Optional[Any]) -> List[str]:
        """Normalize candidates from comma-separated string, list, or empty."""
        if not candidates_input:
            return []
        if isinstance(candidates_input, list):
            res = []
            for item in candidates_input:
                if isinstance(item, str):
                    for part in item.split(","):
                        cleaned = part.strip()
                        if cleaned and cleaned not in res:
                            res.append(cleaned)
                elif isinstance(item, dict) and "name" in item:
                    res.append(item["name"].strip())
            return res
        if isinstance(candidates_input, str):
            res = []
            for part in candidates_input.split(","):
                cleaned = part.strip()
                if cleaned and cleaned not in res:
                    res.append(cleaned)
            return res
        return []

    def generate_plan(
        self,
        candidates: List[str],
        user_query: Optional[str] = None,
        existing_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate complete 4-phase research plan and recursive gap-analysis queries."""
        phase1_queries = self._build_phase1_queries(candidates, user_query)
        phase2_queries = self._build_phase2_queries(candidates)
        phase3_queries = self._build_phase3_queries(candidates)
        phase4_queries = self._build_phase4_queries(candidates)

        total_queries = (
            len(phase1_queries)
            + len(phase2_queries)
            + len(phase3_queries)
            + len(phase4_queries)
        )

        phases = [
            {
                "phase_number": 1,
                "name": "Phase 1: Breadth Market Landscape & Candidate Scouting",
                "objective": "Identify market contenders across Budget, Mid-Range, and Flagship tiers, capture net effective landing prices (accounting for card/seasonal discounts), and compile base manufacturer specifications.",
                "target_dimensions": ["pricing_landing", "variants_skus", "msrp_vs_street"],
                "queries": phase1_queries,
            },
            {
                "phase_number": 2,
                "name": "Phase 2: RTINGS-Style Objective Lab Benchmarks",
                "objective": "Harvest verifiable, reproducible laboratory benchmark data (panel lux/nits, color Delta-E, sustained thermal throttling, motor wattage, decibels dB, active % wt/vol) from technical testing authorities.",
                "target_dimensions": [d["id"] for d in self.profile["required_dimensions"] if "lab" in d["id"] or "thermals" in d["id"] or "efficiency" in d["id"] or "active" in d["id"] or "frequency" in d["id"]],
                "lab_metrics_sought": self.profile["lab_metrics"],
                "queries": phase2_queries,
            },
            {
                "phase_number": 3,
                "name": "Phase 3: Wirecutter-Style Teardown & Long-Term Defect Mining",
                "objective": "Scour authentic community forums (Reddit enthusiast subs, repair technician logs, teardown channels) for 6-12 month durability trends, structural failure modes, and post-update regressions.",
                "target_dimensions": ["defect_rate", "build_repairability", "chassis_teardown"],
                "known_failure_modes_checked": self.profile["known_failure_modes"],
                "queries": phase3_queries,
            },
            {
                "phase_number": 4,
                "name": "Phase 4: Local Ecosystem & Statutory Compliance",
                "objective": "Audit brand authorized service center network reach, turnaround times (TAT), statutory certifications (BIS/BEE/FSSAI/FCC/CE), environmental resilience (voltage surges, coastal corrosion, hard water), and authorized seller channels.",
                "target_dimensions": ["local_service_tat", "statutory_certifications", "environmental_resilience", "authorized_channels"],
                "regional_context": {
                    "region": self.regional_info["name"],
                    "safety": self.regional_info["safety_regulators"],
                    "energy": self.regional_info["energy_regulators"],
                    "climate": self.regional_info["climate_factors"],
                },
                "queries": phase4_queries,
            },
        ]

        # Run recursive gap analysis
        gap_analysis = self._run_gap_analysis(candidates, existing_data)

        return {
            "category": self.category,
            "category_display": self.profile["display_name"],
            "region": self.region_code,
            "region_name": self.regional_info["name"],
            "candidates": candidates,
            "total_queries": total_queries,
            "confidence_threshold": self.confidence_threshold,
            "phases": phases,
            "gap_analysis": gap_analysis,
        }

    # -------------------------------------------------------------------------
    # Phase Query Generators
    # -------------------------------------------------------------------------

    def _build_phase1_queries(self, candidates: List[str], user_query: Optional[str]) -> List[Dict[str, str]]:
        queries = []
        reg = self.regional_info["name"]
        curr = self.regional_info["currency_symbol"]
        curr_code = self.regional_info["currency"]
        cat_clean = self.category.replace("_", " ")

        if not candidates:
            # Broad tier scouting queries: Budget, Mid-Range, Flagship
            queries.append({
                "id": "Q1.1",
                "target": "Budget Entry-Tier Scouting",
                "query": f'best budget {cat_clean} under {curr} {reg} 2025 2026 site:reddit.com OR inurl:review',
                "operator_type": "inurl_review_and_reddit",
            })
            queries.append({
                "id": "Q1.2",
                "target": "Mid-Range Sweet Spot Scouting",
                "query": f'best value for money mid range {cat_clean} {reg} ({curr} OR {curr_code}) inurl:review',
                "operator_type": "inurl_review",
            })
            queries.append({
                "id": "Q1.3",
                "target": "Premium Flagship Contenders",
                "query": f'top flagship premium {cat_clean} comparison {reg} 2025 2026 inurl:comparison',
                "operator_type": "inurl_comparison",
            })
            queries.append({
                "id": "Q1.4",
                "target": "E-Commerce Best Sellers & Net Street Pricing",
                "query": f'top selling {cat_clean} {reg} ({curr} OR {curr_code}) site:amazon.{self.region_code.lower() if self.region_code.lower() != "us" else "com"} OR site:flipkart.com',
                "operator_type": "retail_filter",
            })
            queries.append({
                "id": "Q1.5",
                "target": "Comprehensive Spec Sheet & Release Timeline",
                "query": f'{cat_clean} release dates specifications comparison table {reg} 2025 2026 filetype:pdf OR inurl:specs',
                "operator_type": "filetype_pdf_inurl",
            })
            if user_query:
                clean_uq = re.sub(r'[^a-zA-Z0-9\s]', '', user_query).strip()
                queries.append({
                    "id": "Q1.6",
                    "target": "User Query Intent Alignment",
                    "query": f'{clean_uq} {reg} comparison specifications price inurl:review',
                    "operator_type": "intent_targeted",
                })
        else:
            # Candidate-specific queries + Category Context
            queries.append({
                "id": "Q1.0",
                "target": f"Head-to-Head Comparative Overview ({', '.join(candidates[:3])})",
                "query": f'{" vs ".join([f"\"{c}\"" for c in candidates[:3]])} comparison review {reg} inurl:review',
                "operator_type": "head_to_head_inurl",
            })
            for idx, cand in enumerate(candidates, 1):
                queries.append({
                    "id": f"Q1.{idx}a",
                    "target": f"Net Landing Price & Offers ({cand})",
                    "query": f'"{cand}" ("street price" OR "bank offer" OR "discount" OR "effective price") {reg}',
                    "operator_type": "exact_phrase_quotes",
                })
                queries.append({
                    "id": f"Q1.{idx}b",
                    "target": f"Datasheet & Technical Specifications ({cand})",
                    "query": f'"{cand}" ("specifications" OR "datasheet" OR "spec sheet") filetype:pdf OR inurl:specs',
                    "operator_type": "filetype_pdf_inurl",
                })
                queries.append({
                    "id": f"Q1.{idx}c",
                    "target": f"Market Alternatives & Price-Point Rivals ({cand})",
                    "query": f'"{cand}" ("alternatives" OR "competitors" OR "vs" OR "similar") {reg} inurl:review',
                    "operator_type": "competitor_cross_shop",
                })

        return queries

    def _build_phase2_queries(self, candidates: List[str]) -> List[Dict[str, str]]:
        queries = []
        bench_sources = " OR ".join(self.profile["benchmark_sources"][:3])
        cat_clean = self.category.replace("_", " ")

        if not candidates:
            # 5-6 comprehensive lab queries for open scouting
            queries.append({
                "id": "Q2.1",
                "target": "Lab Benchmark Performance Matrix",
                "query": f'{cat_clean} lab test benchmark comparison ({bench_sources})',
                "operator_type": "lab_domain_filter",
            })
            queries.append({
                "id": "Q2.2",
                "target": "Thermal Throttling & Sustained Performance",
                "query": f'{cat_clean} ("sustained performance" OR "throttling" OR "stress test" OR "heat") ({bench_sources})',
                "operator_type": "metric_specific",
            })
            queries.append({
                "id": "Q2.3",
                "target": "Acoustic Noise Levels & Fan/Motor Decibels",
                "query": f'{cat_clean} ("decibels" OR "dB SPL" OR "noise test" OR "fan noise" OR "quiet") ({bench_sources})',
                "operator_type": "noise_measurement",
            })
            queries.append({
                "id": "Q2.4",
                "target": "Energy & Power Consumption Efficiency",
                "query": f'{cat_clean} ("power consumption" OR "energy efficiency" OR "battery life" OR "wattage") ({bench_sources})',
                "operator_type": "energy_efficiency",
            })
            queries.append({
                "id": "Q2.5",
                "target": "Objective Precision & Component Calibration",
                "query": f'{cat_clean} ("delta-e" OR "color accuracy" OR "lux" OR "purity %" OR "active concentration") ({bench_sources})',
                "operator_type": "objective_calibration",
            })
        else:
            for idx, cand in enumerate(candidates, 1):
                # Lab benchmark query 1: Core Lab Measurements
                queries.append({
                    "id": f"Q2.{idx}a",
                    "target": f"Objective Lab Measurements ({cand})",
                    "query": f'"{cand}" ("lux" OR "nits" OR "delta-E" OR "thermals" OR "wattage" OR "decibels") ({bench_sources})',
                    "operator_type": "lab_domain_filter",
                })
                # Lab benchmark query 2: Sustained Load & Throttle
                queries.append({
                    "id": f"Q2.{idx}b",
                    "target": f"Sustained Stress Test & Throttling ({cand})",
                    "query": f'"{cand}" ("sustained" OR "throttling" OR "stress test" OR "thermal throttle" OR "efficiency curve")',
                    "operator_type": "stress_test_audit",
                })
                # Lab benchmark query 3: Acoustic & Power Efficiency
                queries.append({
                    "id": f"Q2.{idx}c",
                    "target": f"Acoustic Noise dB & Power Efficiency ({cand})",
                    "query": f'"{cand}" ("decibels" OR "dB" OR "power consumption" OR "noise level" OR "wattage draw") ("test" OR "measurement")',
                    "operator_type": "acoustic_power_test",
                })
                # Category specific lab deep dive
                if self.category == "smartphones":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"Camera Sensor Lab & PWM Dimming ({cand})",
                        "query": f'"{cand}" ("PWM dimming" OR "flicker" OR "camera sensor" OR "DxOMark" OR "Geekerwan")',
                        "operator_type": "specialized_lab",
                    })
                elif self.category == "laptops":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"Cinebench 30-min Loop & Fan Noise dB ({cand})",
                        "query": f'"{cand}" ("Cinebench loop" OR "fan noise dB" OR "dpc latency" OR "color accuracy") site:notebookcheck.net',
                        "operator_type": "specialized_lab",
                    })
                elif self.category == "inverter_acs":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"BEE ISEER Certificate & Cooling Capacity at 50°C ({cand})",
                        "query": f'"{cand}" ("ISEER" OR "cooling capacity watts" OR "BEE star" OR "ambient 52") (filetype:pdf OR site:beestarlabel.com)',
                        "operator_type": "specialized_lab",
                    })
                elif self.category == "washing_machines":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"Acoustic Spin Noise dB & Motor Wattage ({cand})",
                        "query": f'"{cand}" ("spin noise dB" OR "water consumption" OR "direct drive wattage" OR "wash test") filetype:pdf OR inurl:manual',
                        "operator_type": "specialized_lab",
                    })
                elif self.category == "skincare":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"Active Ingredient Concentration & pH Stability ({cand})",
                        "query": f'"{cand}" ("concentration" OR "percentage" OR "pH level" OR "clinical study") (site:pubmed.ncbi.nlm.nih.gov OR site:incidecoder.com)',
                        "operator_type": "specialized_lab",
                    })
                elif self.category == "supplements":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"Third-Party Lab Purity & Heavy Metal Assay ({cand})",
                        "query": f'"{cand}" ("heavy metals" OR "amino spiking" OR "lab test" OR "certificate of analysis") (site:trustified.in OR site:labdoor.com)',
                        "operator_type": "specialized_lab",
                    })
                elif self.category == "tws_audio":
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"RTINGS Frequency Response & ANC Decibel Attenuation ({cand})",
                        "query": f'"{cand}" ("frequency response" OR "ANC attenuation dB" OR "mic noise reduction" OR "latency ms") site:rtings.com',
                        "operator_type": "specialized_lab",
                    })
                else:
                    queries.append({
                        "id": f"Q2.{idx}d",
                        "target": f"Independent Lab Test & Spec Verification ({cand})",
                        "query": f'"{cand}" ("lab test" OR "calibrated test" OR "stress test" OR "power measurement") inurl:review',
                        "operator_type": "specialized_lab",
                    })

        return queries

    def _build_phase3_queries(self, candidates: List[str]) -> List[Dict[str, str]]:
        queries = []
        cat_clean = self.category.replace("_", " ")
        subreddits = " OR ".join([f"site:reddit.com/{s}" for s in self.profile.get("subreddits", ["r/reddit.com"])[:3]])
        failures = " OR ".join([f'"{f}"' for f in self.profile["known_failure_modes"][:3]])

        if not candidates:
            # 5-6 comprehensive defect & teardown queries for open scouting
            queries.append({
                "id": "Q3.1",
                "target": "Reddit Enthusiast Community Reliability Audit",
                "query": f'({subreddits}) "{cat_clean}" ("reliability" OR "hardware issue" OR "avoid" OR "defect rate") 2024..2026',
                "operator_type": "reddit_community_filter",
            })
            queries.append({
                "id": "Q3.2",
                "target": "Long-Term 6–12 Month Durability Feedback",
                "query": f'site:reddit.com "{cat_clean}" ("6 months later" OR "1 year later" OR "long term review" OR "durability") 2024..2026',
                "operator_type": "reddit_longterm_audit",
            })
            queries.append({
                "id": "Q3.3",
                "target": "Hardware Teardown & Component Quality",
                "query": f'{cat_clean} ("teardown" OR "disassembly" OR "repairability" OR "inside look" OR "build quality") (site:ifixit.com OR site:youtube.com)',
                "operator_type": "teardown_scout",
            })
            queries.append({
                "id": "Q3.4",
                "target": "Known Structural & Failure Modes",
                "query": f'"{cat_clean}" ({failures}) site:reddit.com',
                "operator_type": "known_defect_scout",
            })
            queries.append({
                "id": "Q3.5",
                "target": "Post-Update Regressions & Firmware Glitches",
                "query": f'site:reddit.com "{cat_clean}" ("after update" OR "firmware bug" OR "battery drain" OR "bricked")',
                "operator_type": "software_regression_scout",
            })
        else:
            for idx, cand in enumerate(candidates, 1):
                # Reddit defect mining query
                queries.append({
                    "id": f"Q3.{idx}a",
                    "target": f"Reddit Defect & Failure Mining ({cand})",
                    "query": f'site:reddit.com "{cand}" ("issue" OR "defect" OR "motherboard" OR "failed" OR "not working" OR "dead")',
                    "operator_type": "reddit_community_filter",
                })
                # Long term 6-12 month review
                queries.append({
                    "id": f"Q3.{idx}b",
                    "target": f"6–12 Month Long-Term Durability ({cand})",
                    "query": f'site:reddit.com "{cand}" ("6 months" OR "1 year" OR "long term" OR "after update" OR "battery drain")',
                    "operator_type": "reddit_longterm_audit",
                })
                # Component Teardown & Build Quality
                queries.append({
                    "id": f"Q3.{idx}c",
                    "target": f"Component Teardown & Repairability ({cand})",
                    "query": f'"{cand}" ("teardown" OR "disassembly" OR "inside look" OR "repairability" OR "iFixit")',
                    "operator_type": "teardown_inspection",
                })
                # Category-specific failure modes
                queries.append({
                    "id": f"Q3.{idx}d",
                    "target": f"Specific Recurring Failure Audit ({cand})",
                    "query": f'"{cand}" ({failures}) site:reddit.com',
                    "operator_type": "known_defect_scout",
                })

        return queries

    def _build_phase4_queries(self, candidates: List[str]) -> List[Dict[str, str]]:
        queries = []
        reg_name = self.regional_info["name"]
        reg_terms = self.regional_info["key_search_terms"]
        cat_clean = self.category.replace("_", " ")

        if not candidates:
            # 5-6 compliance & local readiness queries for open scouting
            queries.append({
                "id": "Q4.1",
                "target": "Statutory Certifications & Energy Standard",
                "query": f'{cat_clean} certification standard ({reg_terms})',
                "operator_type": "statutory_compliance",
            })
            queries.append({
                "id": "Q4.2",
                "target": "Brand Authorized Service Networks & Turnaround Time",
                "query": f'{cat_clean} brand authorized service network turnaround time {reg_name} (site:consumercomplaints.in OR site:reddit.com)',
                "operator_type": "service_network_audit",
            })
            queries.append({
                "id": "Q4.3",
                "target": "Regional Climate & Environmental Resilience",
                "query": f'{cat_clean} ("voltage fluctuation" OR "stabilizer" OR "hard water" OR "humidity" OR "rust" OR "heat") {reg_name}',
                "operator_type": "climate_resilience_audit",
            })
            queries.append({
                "id": "Q4.4",
                "target": "Warranty Terms & Out-of-Warranty Spare Parts Pricing",
                "query": f'{cat_clean} ("warranty terms" OR "out of warranty" OR "spare parts cost" OR "service charge") {reg_name}',
                "operator_type": "warranty_clause_audit",
            })
            queries.append({
                "id": "Q4.5",
                "target": "Authorized Seller Verification & Grey-Market Import Risks",
                "query": f'{cat_clean} ("authorized seller" OR "official warranty" OR "grey market" OR "fake") {reg_name}',
                "operator_type": "authorized_distributor_check",
            })
        else:
            for idx, cand in enumerate(candidates, 1):
                brand = cand.split()[0] if cand.split() else cand
                forums = self.regional_info.get("consumer_forums", "site:reddit.com")
                # Service Network & TAT
                queries.append({
                    "id": f"Q4.{idx}a",
                    "target": f"Authorized Service TAT & Center Reach ({brand})",
                    "query": f'"{brand}" ("service center" OR "repair turnaround" OR "delay" OR "complaint") {reg_name} ({forums})',
                    "operator_type": "service_tat_search",
                })
                # Out-of-warranty cost & spare parts
                queries.append({
                    "id": f"Q4.{idx}b",
                    "target": f"Warranty Clauses & Spare Parts Availability ({cand})",
                    "query": f'"{cand}" ("warranty terms" OR "out of warranty" OR "spare parts cost" OR "replacement policy") {reg_name}',
                    "operator_type": "warranty_clause_audit",
                })
                # Environmental & Climate Resilience
                queries.append({
                    "id": f"Q4.{idx}c",
                    "target": f"Regional Environmental Resilience ({cand})",
                    "query": f'"{cand}" ("voltage fluctuation" OR "stabilizer" OR "hard water" OR "humidity" OR "rust" OR "overheating in summer")',
                    "operator_type": "climate_resilience_audit",
                })
                # Grey market vs authorized sellers
                queries.append({
                    "id": f"Q4.{idx}d",
                    "target": f"Authorized Seller Verification & Official Warranty ({cand})",
                    "query": f'"{cand}" ("authorized seller" OR "official warranty" OR "grey market" OR "import warranty") {reg_name}',
                    "operator_type": "authorized_distributor_check",
                })

        return queries

    # -------------------------------------------------------------------------
    # Recursive Gap Analysis Heuristics
    # -------------------------------------------------------------------------

    def _run_gap_analysis(
        self,
        candidates: List[str],
        existing_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates candidate data points against required dimensions.
        Computes overall completeness and generates follow-up disambiguation queries
        for any dimension with confidence below the threshold.
        """
        required_dims = self.profile["required_dimensions"]
        candidate_evals = {}
        total_dim_count = 0
        total_verified_count = 0

        # If existing_data is provided, parse candidates from it
        data_candidates = {}
        if existing_data and isinstance(existing_data, dict):
            for c in existing_data.get("candidates", []):
                if isinstance(c, dict) and "name" in c:
                    data_candidates[c["name"]] = c

        target_candidates = candidates if candidates else list(data_candidates.keys())
        if not target_candidates:
            # Category-level gap analysis when no candidates specified
            target_candidates = [f"Category: {self.category.replace('_', ' ').title()}"]

        for cand_name in target_candidates:
            cand_data = data_candidates.get(cand_name, {})
            scores = cand_data.get("scores", {})
            specs = cand_data.get("specifications", {})
            findings = cand_data.get("findings", {})

            dim_statuses = {}
            missing_dims = []
            disambiguation_queries = []

            for dim in required_dims:
                dim_id = dim["id"]
                priority = dim["priority"]
                label = dim["label"]

                # Check if dimension is covered in existing data
                confidence = 0.0
                evidence = ""

                if dim_id in scores:
                    confidence = 0.85
                    evidence = f"Score recorded: {scores[dim_id]}/10"
                elif dim_id in specs or dim_id in findings:
                    confidence = 0.75
                    evidence = f"Spec value recorded: {specs.get(dim_id, findings.get(dim_id))}"
                elif any(k in scores or k in specs for k in [dim_id.split('_')[0], dim_id.split('_')[-1]]):
                    confidence = 0.50
                    evidence = "Partial heuristic match found in candidate data"
                else:
                    confidence = 0.0
                    evidence = "No verified data point logged"

                total_dim_count += 1
                if confidence >= self.confidence_threshold:
                    total_verified_count += 1
                    status = "verified"
                elif confidence > 0.0:
                    status = "partial"
                    missing_dims.append({"id": dim_id, "label": label, "priority": priority, "confidence": confidence})
                else:
                    status = "missing"
                    missing_dims.append({"id": dim_id, "label": label, "priority": priority, "confidence": confidence})

                dim_statuses[dim_id] = {
                    "label": label,
                    "priority": priority,
                    "confidence": round(confidence, 2),
                    "status": status,
                    "evidence": evidence,
                }

                # Generate disambiguation query if confidence is below threshold
                if confidence < self.confidence_threshold:
                    q = self._generate_single_disambiguation_query(cand_name, dim_id, label)
                    disambiguation_queries.append({
                        "dimension_id": dim_id,
                        "dimension_label": label,
                        "priority": priority,
                        "query": q,
                    })

            cand_confidence = (
                sum(d["confidence"] for d in dim_statuses.values()) / len(dim_statuses)
                if dim_statuses else 0.0
            )

            candidate_evals[cand_name] = {
                "candidate_name": cand_name,
                "overall_confidence": round(cand_confidence, 2),
                "is_complete": cand_confidence >= self.confidence_threshold,
                "dimensions": dim_statuses,
                "missing_dimensions": missing_dims,
                "disambiguation_queries": disambiguation_queries,
            }

        overall_ratio = (total_verified_count / total_dim_count) if total_dim_count > 0 else 0.0

        return {
            "status": "complete" if overall_ratio >= self.confidence_threshold else "needs_disambiguation",
            "required_dimension_count": len(required_dims),
            "overall_research_completeness": round(overall_ratio * 100, 1),
            "confidence_threshold": self.confidence_threshold,
            "candidate_evaluations": candidate_evals,
        }

    def _generate_single_disambiguation_query(self, candidate_name: str, dim_id: str, label: str) -> str:
        """Formulate high-precision targeted disambiguation search query for a missing dimension."""
        c = candidate_name.replace("Category: ", "")
        reg = self.regional_info["name"]

        if "pricing" in dim_id:
            return f'"{c}" ("net price" OR "effective price" OR "card discount" OR "lowest price") {reg}'
        if "thermals" in dim_id or "throttling" in dim_id:
            return f'"{c}" ("sustained thermal throttle" OR "wattage draw" OR "temperature test" OR "heat") site:notebookcheck.net OR site:ultrabookreview.com'
        if "display" in dim_id:
            return f'"{c}" ("measured nits" OR "peak lux" OR "color accuracy delta-e" OR "PWM frequency") (site:rtings.com OR site:notebookcheck.net)'
        if "camera" in dim_id:
            return f'"{c}" ("camera sensor size" OR "low light photo samples" OR "OIS performance") site:gsmarena.com OR site:dxomark.com'
        if "battery" in dim_id:
            return f'"{c}" ("battery drain test" OR "active runtime hours" OR "charge cycle degradation")'
        if "defect" in dim_id:
            return f'site:reddit.com "{c}" ("known defect" OR "common failure" OR "dead" OR "motherboard" OR "green line")'
        if "build" in dim_id or "repairability" in dim_id or "teardown" in dim_id:
            return f'"{c}" ("teardown" OR "disassembly" OR "chassis build" OR "hinge" OR "repairability") (site:ifixit.com OR site:youtube.com)'
        if "service" in dim_id or "tat" in dim_id:
            forums = self.regional_info.get("consumer_forums", "site:reddit.com")
            return f'"{c}" ("authorized service turnaround" OR "repair delay" OR "service experience") {reg} ({forums})'
        if "iseer" in dim_id or "efficiency" in dim_id:
            return f'"{c}" ("BEE star rating" OR "ISEER" OR "energy consumption per year" OR "lab test report")'
        if "condenser" in dim_id:
            return f'"{c}" ("100% copper condenser" OR "aluminum coil" OR "blue fin coating") filetype:pdf OR inurl:brochure'
        if "motor" in dim_id or "spider" in dim_id:
            return f'"{c}" ("direct drive" OR "spider arm corrosion" OR "tub bearing" OR "drum material")'
        if "stabilizer" in dim_id or "voltage" in dim_id:
            return f'"{c}" ("stabilizer free" OR "operating voltage range" OR "voltage surge") {reg}'
        if "hard_water" in dim_id:
            return f'"{c}" ("hard water" OR "descaling" OR "scale buildup" OR "water softener")'
        if "active" in dim_id or "purity" in dim_id:
            return f'"{c}" ("active concentration %" OR "certificate of analysis" OR "third party lab report" OR "heavy metals")'
        if "amino" in dim_id:
            return f'"{c}" ("amino spiking" OR "glycine spiking" OR "heavy metals test" OR "lab test") site:trustified.in OR site:labdoor.com'
        if "comedogenic" in dim_id or "ph_" in dim_id:
            return f'"{c}" ("comedogenic" OR "pore clogging" OR "pH level" OR "irritation") site:incidecoder.com'
        if "clinical" in dim_id:
            return f'"{c}" ("clinical study" OR "double blind" OR "in vivo" OR "efficacy trial") site:pubmed.ncbi.nlm.nih.gov'
        if "frequency" in dim_id or "sound" in dim_id:
            return f'"{c}" ("frequency response curve" OR "Harman target" OR "measured ANC dB") site:rtings.com OR site:crinacle.com'
        if "codec" in dim_id or "latency" in dim_id:
            return f'"{c}" ("LDAC" OR "aptX" OR "Bluetooth latency ms" OR "supported codecs")'
        if "warranty" in dim_id:
            return f'"{c}" ("warranty terms" OR "out of warranty cost" OR "service policy") {reg}'
        
        # Generic fallback disambiguation query
        return f'"{c}" "{label}" ("test" OR "review" OR "specifications" OR "verified")'

    # -------------------------------------------------------------------------
    # Markdown Rendering
    # -------------------------------------------------------------------------

    def render_markdown(self, plan: Dict[str, Any]) -> str:
        """Render publication-grade research plan in GitHub-flavored Markdown."""
        lines = []
        cat_disp = plan["category_display"]
        reg = plan["region_name"]
        curr = self.regional_info["currency_symbol"]
        curr_code = self.regional_info["currency"]
        candidates = plan["candidates"]
        total_q = plan["total_queries"]
        thresh = plan["confidence_threshold"]
        gap = plan["gap_analysis"]

        lines.append(f"# Multi-Agent Deep Research & Query Fan-Out Plan: {cat_disp}")
        lines.append("")
        lines.append(f"> **Target Region:** {reg} ({plan['region']}) | **Currency:** {curr} ({curr_code}) | **Generated Queries:** {total_q} | **Confidence Gate:** {thresh*100:.0f}%")
        lines.append("")

        if candidates:
            cand_str = ", ".join([f"`{c}`" for c in candidates])
            lines.append(f"**Target Contenders ({len(candidates)}):** {cand_str}")
        else:
            lines.append("**Target Contenders:** _Open Market Landscape Scouting (Budget, Mid-Range, Flagship)_")
        lines.append("")

        # Architecture Overview Diagram
        lines.append("## Research Architecture & Query Fan-Out Topology")
        lines.append("")
        lines.append("```mermaid")
        lines.append("flowchart TD")
        lines.append('    P1["Phase 1: Breadth Market Landscape\\n(Pricing, Variants, SKUs)"]')
        lines.append('    P2["Phase 2: RTINGS-Style Lab Benchmarks\\n(Lux, Thermals, Delta-E, Watts, dB)"]')
        lines.append('    P3["Phase 3: Wirecutter-Style Teardown\\n(Reddit Sentiment, 6-12 Mo Defects)"]')
        lines.append('    P4["Phase 4: Local Ecosystem & Compliance\\n(Service TAT, BIS/BEE/FSSAI, Climate)"]')
        lines.append('    Gap["Recursive Gap-Analysis Engine\\n(Confidence Check < Threshold)"]')
        lines.append('    Synth["Grounded Synthesis & Scorer\\n(product_scorer.py)"]')
        lines.append("")
        lines.append("    P1 --> P2 --> P3 --> P4 --> Gap")
        lines.append('    Gap -- "Confidence < Threshold" --> Disambig["Phase 5: Precision Disambiguation Queries"]')
        lines.append("    Disambig --> Gap")
        lines.append('    Gap -- "Confidence >= Threshold" --> Synth')
        lines.append("```")
        lines.append("")

        # Phases and Executable Queries
        lines.append("---")
        lines.append("## Multi-Phase Research Execution Vectors")
        lines.append("")

        for phase in plan["phases"]:
            p_name = phase["name"]
            p_obj = phase["objective"]
            queries = phase["queries"]

            lines.append(f"### {p_name}")
            lines.append(f"**Objective:** {p_obj}")
            lines.append("")

            if "lab_metrics_sought" in phase:
                lines.append("**Lab Metrics Targeted:** " + ", ".join([f"`{m}`" for m in phase["lab_metrics_sought"]]))
                lines.append("")
            if "known_failure_modes_checked" in phase:
                lines.append("**Failure Modes Monitored:** " + ", ".join([f"`{f}`" for f in phase["known_failure_modes_checked"]]))
                lines.append("")

            lines.append(f"| Query ID | Target Inquiry Vector | Operator Type | Executable Search Query |")
            lines.append(f"| :--- | :--- | :--- | :--- |")
            for q in queries:
                q_text = q["query"].replace("|", "\\|")
                lines.append(f"| `{q['id']}` | **{q['target']}** | `{q['operator_type']}` | `{q_text}` |")
            lines.append("")

        # Recursive Gap Analysis Section
        lines.append("---")
        lines.append("## Recursive Gap-Analysis & Disambiguation Engine")
        lines.append("")
        lines.append(f"- **Current Research Completeness:** **{gap['overall_research_completeness']}%**")
        lines.append(f"- **Engine Status:** `[{gap['status'].upper()}]` (Confidence Threshold: `{thresh*100:.0f}%`)")
        lines.append("")

        for cand_name, eval_info in gap["candidate_evaluations"].items():
            lines.append(f"#### Contender: {cand_name} (Completeness: {eval_info['overall_confidence']*100:.0f}%)")
            lines.append("")
            lines.append("| Dimension | Priority | Status | Confidence | Current Evidence / Finding |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for dim_id, d in eval_info["dimensions"].items():
                status_icon = "✅" if d["status"] == "verified" else ("⚠️" if d["status"] == "partial" else "❌")
                lines.append(f"| {d['label']} | `{d['priority']}` | {status_icon} `{d['status']}` | `{d['confidence']*100:.0f}%` | {d['evidence']} |")
            lines.append("")

            if eval_info["disambiguation_queries"]:
                lines.append(f"**Phase 5: Precision Disambiguation Fan-Out for {cand_name}:**")
                lines.append("")
                for dq in eval_info["disambiguation_queries"]:
                    lines.append(f"- `[{dq['priority'].upper()}]` **{dq['dimension_label']}**:")
                    lines.append(f"  ```text\n  {dq['query']}\n  ```")
                lines.append("")

        # Execution Guidelines for Agents
        lines.append("---")
        lines.append("## Autonomous Agent Execution Guidelines")
        lines.append("")
        lines.append("1. **Scout Wave 1 (Breadth):** Deploy parallel search workers across Phase 1 queries. Extract candidate pricing, specs, and variants.")
        lines.append("2. **Scout Wave 2 (Lab & Teardown):** Run Phase 2 (lab benchmarks) and Phase 3 (defect mining) queries. Extract hard numbers (lux, dB, watts, failure logs).")
        lines.append("3. **Scout Wave 3 (Compliance):** Run Phase 4 queries to establish authorized service centers and regional compliance.")
        lines.append("4. **Recursive Gap Resolution:** Inspect extracted facts against the Gap Analysis Matrix. Execute Phase 5 queries for any dimension under the threshold.")
        lines.append("5. **Deterministic Pass-Off:** Feed gathered dimensional scores into `scripts/product_scorer.py` for mathematical ranking.")
        lines.append("")

        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Main CLI Interface
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Multi-Agent Deep Research & Query Fan-Out Planner"
    )
    parser.add_argument(
        "-c", "--category",
        required=True,
        help="Product category (e.g., smartphones, laptops, inverter_acs, washing_machines, skincare, supplements, tws_audio, or custom)",
    )
    parser.add_argument(
        "-p", "--candidates",
        default="",
        help="Comma-separated candidate product names (e.g. 'iPhone 16 Pro, Galaxy S24 Ultra, Pixel 9 Pro')",
    )
    parser.add_argument(
        "-r", "--region",
        default="IN",
        help="Target geographic region / jurisdiction code (e.g. IN, US, EU, UK). Default: IN",
    )
    parser.add_argument(
        "-q", "--query",
        default="",
        help="Raw user query to align intent and context",
    )
    parser.add_argument(
        "-d", "--data",
        default=None,
        help="Path to JSON file or raw JSON string containing existing candidate data for recursive gap analysis",
    )
    parser.add_argument(
        "-t", "--confidence-threshold",
        type=float,
        default=0.70,
        help="Confidence threshold for recursive gap-analysis heuristics (default: 0.70)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output plan in structured machine-readable JSON format",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output plan in formatted GitHub-flavored Markdown (default)",
    )

    args = parser.parse_args()

    planner = ResearchPlanner(
        category=args.category,
        region=args.region,
        confidence_threshold=args.confidence_threshold,
    )

    candidates = planner.parse_candidates(args.candidates)

    existing_data = None
    if args.data:
        try:
            if os.path.isfile(args.data):
                with open(args.data, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            else:
                existing_data = json.loads(args.data)
        except Exception as e:
            sys.stderr.write(f"[WARN] Failed to load gap-analysis data from {args.data}: {e}\n")

    plan = planner.generate_plan(
        candidates=candidates,
        user_query=args.query,
        existing_data=existing_data,
    )

    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print(planner.render_markdown(plan))


if __name__ == "__main__":
    main()
