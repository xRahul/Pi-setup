#!/usr/bin/env python3
"""
Automated Test Suite for Citation Tree Compiler & Deep Research Report Compiler
Verifies:
  1. Citation Compilation, Authority Tiering (Tiers 1, 2, 3), and Provenance Footnotes
  2. End-to-End Report Compiler assembly across all 10 Publication-Grade Sections
  3. Mermaid flowchart syntax, 3-year TCO model, Sensitivity analysis, and Defect audit
  4. Full Pipeline Integration: defect_miner -> metric_extractor -> product_scorer -> citation_compiler -> report_compiler
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from citation_compiler import (
    classify_authority_tier,
    compile_citations,
    demux_citation_input,
    extract_domain,
    extract_sources_from_raw_text,
    link_citations_in_text,
    normalize_url,
    render_citation_tree_markdown,
)
from report_compiler import (
    build_candidate_engineering_section,
    build_parameter_weights_table,
    build_persona_mermaid_and_table,
    build_quick_winners,
    build_tco_table_and_notes,
    compile_publication_dossier,
    validate_dossier_markdown,
)


class TestCitationCompiler(unittest.TestCase):
    """Verifies authority tiering, URL cleaning, deduplication, and footnote generation."""

    def test_authority_tier_domain_classification(self):
        # Tier 1: Lab / Teardown / Statutory
        t1_urls = [
            "https://www.rtings.com/tv/reviews/lg/c3-oled",
            "https://notebookcheck.net/Apple-MacBook-Pro-16-review.html",
            "https://www.ifixit.com/Teardown/iPhone+15+Pro+Teardown/12345",
            "https://bis.gov.in/standards/electronics/r-12345",
            "https://beeindia.gov.in/appliances/inverter-ac-star-rating",
            "https://fcc.gov/oet/ea/fccid",
        ]
        for url in t1_urls:
            tier_num, tier_label, score = classify_authority_tier(url)
            self.assertEqual(tier_num, 1, f"Expected Tier 1 for {url}, got {tier_num}")
            self.assertIn("Tier 1", tier_label)
            self.assertGreaterEqual(score, 90.0)

        # Tier 2: Technical Media / Specialist
        t2_urls = [
            "https://www.gsmarena.com/samsung_galaxy_s24-review-123.php",
            "https://www.theverge.com/2024/1/1/oneplus-12-review",
            "https://arstechnica.com/gadgets/2024/02/apple-vision-pro-review/",
            "https://www.tomshardware.com/pc-components/cpus/amd-ryzen-7-7800x3d-review",
        ]
        for url in t2_urls:
            tier_num, tier_label, score = classify_authority_tier(url)
            self.assertEqual(tier_num, 2, f"Expected Tier 2 for {url}, got {tier_num}")
            self.assertIn("Tier 2", tier_label)

        # Tier 3: Community / Reddit / Owner Forums
        t3_urls = [
            "https://www.reddit.com/r/oneplus/comments/xyz123/green_line_after_update/",
            "https://forum.xda-developers.com/t/samsung-s24-battery-drain.456/",
            "https://forums.macrumors.com/threads/m3-macbook-pro-thermal-throttling.123/",
            "https://www.team-bhp.com/forum/technical-stuff/12345-car-inverter-issue.html",
        ]
        for url in t3_urls:
            tier_num, tier_label, score = classify_authority_tier(url)
            self.assertEqual(tier_num, 3, f"Expected Tier 3 for {url}, got {tier_num}")
            self.assertIn("Tier 3", tier_label)

    def test_url_normalization_and_deduplication(self):
        url_with_tracking = "https://www.rtings.com/tv/reviews/samsung/s90c?utm_source=google&utm_medium=cpc&ref=affiliate"
        clean = normalize_url(url_with_tracking)
        self.assertEqual(clean, "https://www.rtings.com/tv/reviews/samsung/s90c")
        self.assertNotIn("utm_source", clean)
        self.assertNotIn("ref=", clean)

        # Deduplication in compile_citations
        raw_list = [
            {"url": "https://www.rtings.com/headphones/test-1", "snippet": "Snippet A", "claim": "Low latency"},
            {"url": "https://www.rtings.com/headphones/test-1?utm_campaign=winter", "snippet": "Snippet B", "claim": "Durable headband"},
        ]
        compiled = compile_citations(raw_list)
        self.assertEqual(compiled["total_sources"], 1)
        c0 = compiled["citations"][0]
        self.assertEqual(len(c0["snippets"]), 2)
        self.assertIn("Low latency", c0["claims"])
        self.assertIn("Durable headband", c0["claims"])

    def test_claim_to_source_provenance_and_footnotes(self):
        sources = [
            {"url": "https://www.rtings.com/monitor/test", "title": "RTINGS Monitor Benchmark", "tier": 1},
            {"url": "https://www.theverge.com/review", "title": "The Verge In-Depth", "tier": 2},
            {"url": "https://reddit.com/r/hardware/thread", "title": "Reddit Reliability Discussion", "tier": 3},
        ]
        compiled = compile_citations(sources)
        md = render_citation_tree_markdown(compiled)

        self.assertIn("## 10. Complete Evidence Citation Tree & Source Bibliography", md)
        self.assertIn("Tier 1: Lab, Teardown & Statutory Sources", md)
        self.assertIn("Tier 2: Technical Media & Specialist Publications", md)
        self.assertIn("Tier 3: Authentic Community & Owner Megathreads", md)
        self.assertIn("[^1]:", md)
        self.assertIn("[^2]:", md)
        self.assertIn("[^3]:", md)

    def test_link_citations_in_text(self):
        citation_tree = {
            "citations": [
                {"id": 1, "ref": "[^1]", "url": "https://www.rtings.com/display-test", "domain": "rtings.com"}
            ]
        }
        text = "Lab measurements show high brightness in [RTINGS Display Analysis](https://www.rtings.com/display-test)."
        linked = link_citations_in_text(text, citation_tree)
        self.assertIn("[RTINGS Display Analysis](https://www.rtings.com/display-test) [^1]", linked)


class TestReportCompiler(unittest.TestCase):
    """Verifies report compilation, section completeness, Mermaid diagrams, and TCO model."""

    def setUp(self):
        self.scorer_data = {
            "category": "smartphones",
            "currency": "INR",
            "normalized_weights": {
                "performance": 0.30,
                "display": 0.20,
                "camera": 0.20,
                "battery_charging": 0.15,
                "build_durability": 0.15,
            },
            "champions": {
                "overall_winner": {"name": "Flagship Pro X", "tier": "flagship", "price": 69999.0, "final_score": 8.85, "vfm_index": 12.6},
                "vfm_champion": {"name": "Mid Value 5G", "tier": "midrange", "price": 49999.0, "final_score": 8.60, "vfm_index": 17.2},
                "tier_champions": {
                    "budget": {"name": "Budget Champ A1", "tier": "budget", "price": 19999.0, "final_score": 7.75, "vfm_index": 38.7},
                    "midrange": {"name": "Mid Value 5G", "tier": "midrange", "price": 49999.0, "final_score": 8.60, "vfm_index": 17.2},
                    "flagship": {"name": "Flagship Pro X", "tier": "flagship", "price": 69999.0, "final_score": 8.85, "vfm_index": 12.6},
                },
            },
            "ranked_candidates": [
                {
                    "rank": 1,
                    "name": "Flagship Pro X",
                    "tier": "flagship",
                    "price": 69999.0,
                    "readiness_factor": 1.0,
                    "confidence_score": 96.0,
                    "confidence_tier": "HIGH (Verified Lab/Teardown)",
                    "final_score": 8.85,
                    "vfm_index": 12.6,
                    "rank_stability_pct": 98.0,
                    "stability_tier": "Solid",
                    "parameter_scores": {"performance": 9.2, "display": 9.4, "camera": 9.0, "battery_charging": 8.4, "build_durability": 9.0},
                },
                {
                    "rank": 2,
                    "name": "Mid Value 5G",
                    "tier": "midrange",
                    "price": 49999.0,
                    "readiness_factor": 0.98,
                    "confidence_score": 92.0,
                    "confidence_tier": "HIGH (Verified Lab/Teardown)",
                    "final_score": 8.60,
                    "vfm_index": 17.2,
                    "rank_stability_pct": 88.0,
                    "stability_tier": "Solid",
                    "parameter_scores": {"performance": 9.0, "display": 8.8, "camera": 8.4, "battery_charging": 9.2, "build_durability": 8.2},
                },
                {
                    "rank": 3,
                    "name": "Budget Champ A1",
                    "tier": "budget",
                    "price": 19999.0,
                    "readiness_factor": 0.94,
                    "confidence_score": 86.0,
                    "confidence_tier": "HIGH (Verified Lab/Teardown)",
                    "final_score": 7.75,
                    "vfm_index": 38.7,
                    "rank_stability_pct": 80.0,
                    "stability_tier": "Moderate",
                    "parameter_scores": {"performance": 8.0, "display": 7.8, "camera": 7.0, "battery_charging": 8.4, "build_durability": 7.5},
                },
            ],
            "sensitivity_analysis": {
                "monte_carlo_iterations": 100,
                "weight_perturbation_range": "±15%",
                "winner_robustness": 98.0,
                "candidate_stability": {"Flagship Pro X": 98.0, "Mid Value 5G": 88.0, "Budget Champ A1": 80.0},
                "flipping_thresholds": [
                    {"candidate_1": "Flagship Pro X", "candidate_2": "Mid Value 5G", "parameter": "display", "score_delta_needed": 0.55, "price_drop_needed_pct": 8.2}
                ],
            },
        }

        self.defect_data = {
            "category": "smartphones",
            "currency": "INR",
            "candidates": [
                {
                    "name": "Mid Value 5G",
                    "tier": "midrange",
                    "price": 49999.0,
                    "defects": [
                        {"issue": "Aggressive background app closure", "severity": "minor", "affects": "software_support", "defect_type": "batch_variance", "source_count": 4}
                    ],
                }
            ],
        }

        # 10 realistic sources across 3 tiers
        sources = []
        for i in range(1, 5):
            sources.append({"url": f"https://www.rtings.com/phone/test-{i}", "title": f"RTINGS Lab Suite #{i}", "tier": 1, "phase": "Phase 2: Lab & Teardowns"})
        for i in range(1, 4):
            sources.append({"url": f"https://www.gsmarena.com/review-{i}", "title": f"GSMArena Deep Test #{i}", "tier": 2, "phase": "Phase 1: Broad Landscape"})
        for i in range(1, 4):
            sources.append({"url": f"https://www.reddit.com/r/phone/thread-{i}", "title": f"Reddit Defect Thread #{i}", "tier": 3, "phase": "Phase 3: Defect & Longevity Mining"})

        self.citation_data = compile_citations(sources)

    def test_report_assembly_all_10_sections(self):
        dossier = compile_publication_dossier(
            scorer_data=self.scorer_data,
            defect_data=self.defect_data,
            citation_data=self.citation_data,
            metadata={"category": "smartphones", "currency": "INR", "target_region": "India"},
        )

        # Verify all 10 required section headings exist
        for sec_num in range(1, 11):
            pattern = f"## {sec_num}\\."
            self.assertRegex(dossier, pattern, f"Missing section {sec_num} in compiled dossier")

        # Verify no unreplaced template placeholders {{...}}
        unreplaced = [m for m in dossier.split() if m.startswith("{{") and m.endswith("}}")]
        self.assertEqual(unreplaced, [], f"Found unreplaced placeholders: {unreplaced}")

        # Verify publication word count
        words = len(dossier.split())
        self.assertGreaterEqual(words, 2000, f"Dossier word count {words} below publication threshold")

    def test_quick_winners_matrix_and_champions(self):
        qw = build_quick_winners(self.scorer_data, {}, "INR")
        self.assertEqual(qw["flagship"]["name"], "Flagship Pro X")
        self.assertEqual(qw["midrange"]["name"], "Mid Value 5G")
        self.assertEqual(qw["budget"]["name"], "Budget Champ A1")
        self.assertEqual(qw["vfm"]["name"], "Mid Value 5G")
        self.assertIn("₹", qw["flagship"]["price"])

    def test_mermaid_flowchart_generation(self):
        mermaid, p_table = build_persona_mermaid_and_table(self.scorer_data["ranked_candidates"], {})
        self.assertTrue(mermaid.startswith("flowchart TD"))
        self.assertIn("Flagship Pro X", mermaid)
        self.assertIn("Mid Value 5G", mermaid)
        self.assertIn("Budget Champ A1", mermaid)
        self.assertIn("| Buyer Persona / Profile |", p_table)

    def test_tco_depreciation_model(self):
        tco_table, notes = build_tco_table_and_notes(self.scorer_data["ranked_candidates"], "INR", "smartphones")
        self.assertIn("Acquisition Cost (Net)", tco_table)
        self.assertIn("3-Year Energy / Utility Cost", tco_table)
        self.assertIn("Year 3 Residual Salvage Value", tco_table)
        self.assertIn("Net 3-Year TCO", tco_table)
        self.assertIn("Flagship Pro X", tco_table)
        self.assertIn("₹", tco_table)
        self.assertIn("Lifecycle Advisory", notes)

    def test_validation_pass_and_failure_modes(self):
        dossier = compile_publication_dossier(
            scorer_data=self.scorer_data,
            defect_data=self.defect_data,
            citation_data=self.citation_data,
            metadata={"category": "smartphones", "currency": "INR"},
        )
        is_valid, errors = validate_dossier_markdown(dossier)
        self.assertTrue(is_valid, f"Validation failed unexpectedly: {errors}")
        self.assertEqual(errors, [])

        # Test failure mode: truncated markdown missing sections
        bad_markdown = "# Minimal Report\n\n## 1. Executive Summary\nOnly one section."
        is_valid_bad, errors_bad = validate_dossier_markdown(bad_markdown)
        self.assertFalse(is_valid_bad)
        self.assertGreater(len(errors_bad), 3)


class TestEndToEndPipeline(unittest.TestCase):
    """Verifies end-to-end execution across the 5 CLI tools."""

    def test_full_pipeline_cli_execution(self):
        # 1. Defect Miner
        sample_defect_input = """
        [Contender Alpha] Teardown shows 100% electrolytic copper coil with gold fin. Sustained 3DMark 88%.
        [Contender Beta] Reddit r/tech: Users report minor camera island fogging in high humidity.
        """
        dm_proc = subprocess.run(
            [
                os.path.join(SCRIPTS_DIR, "defect_miner.py"),
                "--text", sample_defect_input,
                "-c", "smartphones",
                "--to-extractor-json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        extractor_input = json.loads(dm_proc.stdout)
        self.assertIn("candidates", extractor_input)

        # 2. Metric Extractor
        me_proc = subprocess.run(
            [os.path.join(SCRIPTS_DIR, "metric_extractor.py")],
            input=json.dumps(extractor_input),
            capture_output=True,
            text=True,
            check=True,
        )
        scorer_input = json.loads(me_proc.stdout)
        self.assertIn("candidates", scorer_input)

        # 3. Product Scorer
        ps_proc = subprocess.run(
            [os.path.join(SCRIPTS_DIR, "product_scorer.py"), "--json", "--mc-iterations", "20"],
            input=json.dumps(scorer_input),
            capture_output=True,
            text=True,
            check=True,
        )
        scorer_output = json.loads(ps_proc.stdout)
        self.assertIn("ranked_candidates", scorer_output)
        self.assertIn("sensitivity_analysis", scorer_output)

        # 4. Citation Compiler (12 diverse sources)
        sources = [
            {"url": "https://www.rtings.com/alpha-test", "title": "RTINGS Alpha Lab", "tier": 1},
            {"url": "https://www.ifixit.com/teardown/alpha", "title": "iFixit Teardown", "tier": 1},
            {"url": "https://bis.gov.in/cert/123", "title": "BIS Statutory Compliance", "tier": 1},
            {"url": "https://www.gsmarena.com/alpha-review", "title": "GSMArena Hands-on", "tier": 2},
            {"url": "https://www.theverge.com/alpha-review", "title": "The Verge In-depth", "tier": 2},
            {"url": "https://www.anandtech.com/alpha-soc", "title": "AnandTech Architecture", "tier": 2},
            {"url": "https://reddit.com/r/alpha/comments/123", "title": "Reddit Alpha Thread", "tier": 3},
            {"url": "https://reddit.com/r/beta/comments/456", "title": "Reddit Beta Thread", "tier": 3},
        ]
        cc_proc = subprocess.run(
            [os.path.join(SCRIPTS_DIR, "citation_compiler.py"), "--json"],
            input=json.dumps(sources),
            capture_output=True,
            text=True,
            check=True,
        )
        citation_output = json.loads(cc_proc.stdout)
        self.assertEqual(citation_output["total_sources"], 8)

        # 5. Report Compiler with --validate
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_sc:
            json.dump(scorer_output, f_sc)
            p_sc = f_sc.name
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_df:
            json.dump(extractor_input, f_df)
            p_df = f_df.name
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_ct:
            json.dump(citation_output, f_ct)
            p_ct = f_ct.name
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f_out:
            p_out = f_out.name

        try:
            rc_proc = subprocess.run(
                [
                    os.path.join(SCRIPTS_DIR, "report_compiler.py"),
                    "--scorer-json", p_sc,
                    "--defect-json", p_df,
                    "--citation-json", p_ct,
                    "-o", p_out,
                    "--validate",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(rc_proc.returncode, 0, f"Report compiler failed:\nSTDOUT: {rc_proc.stdout}\nSTDERR: {rc_proc.stderr}")
            self.assertIn("Validation Passed", rc_proc.stderr)

            # Check file on disk
            with open(p_out, "r", encoding="utf-8") as f:
                output_dossier = f.read()

            self.assertIn("## 1. Executive Summary & Quick Winners Matrix", output_dossier)
            self.assertIn("## 10. Complete Evidence Citation Tree & Source Bibliography", output_dossier)
            self.assertGreater(len(output_dossier.split()), 2000)
        finally:
            for p in [p_sc, p_df, p_ct, p_out]:
                if os.path.exists(p):
                    os.unlink(p)


if __name__ == "__main__":
    unittest.main()
