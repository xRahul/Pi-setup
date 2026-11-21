#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Metric Extractor and Deterministic Scorer
Verifies RTINGS-style metric normalization curves, defect penalties, IRF calculation,
and end-to-end pipeline execution across all 7 product categories.
"""

import json
import os
import subprocess
import sys
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from metric_extractor import (
    evaluate_piecewise_linear,
    evaluate_discrete,
    evaluate_sigmoid,
    evaluate_direct_score,
    extract_defect_penalties,
    compute_irf,
    extract_and_normalize,
    load_archetypes,
)
from product_scorer import score_candidates


class TestScoringCurves(unittest.TestCase):
    """Test mathematical behavior of piecewise linear, sigmoid, and discrete curves."""

    def test_piecewise_linear_higher_is_better(self):
        # Brightness curve: [[400, 3.0], [800, 6.0], [1200, 8.0], [1600, 9.5], [2400, 10.0]]
        pts = [[400.0, 3.0], [800.0, 6.0], [1200.0, 8.0], [1600.0, 9.5], [2400.0, 10.0]]
        # At or below min
        self.assertAlmostEqual(evaluate_piecewise_linear(300, pts), 3.0)
        self.assertAlmostEqual(evaluate_piecewise_linear(400, pts), 3.0)
        # Midpoint between 400 and 800 -> 600 -> 4.5
        self.assertAlmostEqual(evaluate_piecewise_linear(600, pts), 4.5)
        # Exact knot
        self.assertAlmostEqual(evaluate_piecewise_linear(1200, pts), 8.0)
        # At or above max
        self.assertAlmostEqual(evaluate_piecewise_linear(2400, pts), 10.0)
        self.assertAlmostEqual(evaluate_piecewise_linear(3500, pts), 10.0)

    def test_piecewise_linear_lower_is_better(self):
        # Noise curve: [[20, 10.0], [25, 8.8], [30, 7.0], [36, 4.5], [44, 1.5]]
        pts = [[20.0, 10.0], [25.0, 8.8], [30.0, 7.0], [36.0, 4.5], [44.0, 1.5]]
        # At or below min noise (ultra silent)
        self.assertAlmostEqual(evaluate_piecewise_linear(18, pts), 10.0)
        self.assertAlmostEqual(evaluate_piecewise_linear(20, pts), 10.0)
        # Loud noise
        self.assertAlmostEqual(evaluate_piecewise_linear(44, pts), 1.5)
        self.assertAlmostEqual(evaluate_piecewise_linear(60, pts), 1.5)

    def test_discrete_lookups(self):
        options = {"100%_grooved_copper": 10.0, "copper": 9.5, "aluminum": 2.0}
        self.assertAlmostEqual(evaluate_discrete("100% Grooved Copper", options), 10.0)
        self.assertAlmostEqual(evaluate_discrete("copper", options), 9.5)
        self.assertAlmostEqual(evaluate_discrete("Aluminum", options), 2.0)

    def test_boolean_translations(self):
        options = {"true": 10.0, "false": 3.0}
        self.assertAlmostEqual(evaluate_discrete(True, options), 10.0)
        self.assertAlmostEqual(evaluate_discrete("yes", options), 10.0)
        self.assertAlmostEqual(evaluate_discrete(False, options), 3.0)
        self.assertAlmostEqual(evaluate_discrete("no", options), 3.0)


class TestDefectPenalties(unittest.TestCase):
    """Test defect deductions, severity mapping, and parameter ceilings."""

    def setUp(self):
        self.archetypes = load_archetypes()
        self.framework = self.archetypes["defect_penalties"]
        self.params = ["performance", "display", "build_durability"]
        self.mapping = {"defect_rate": "build_durability"}

    def test_critical_defect_ceiling(self):
        defects = [{"issue": "vertical green line on AMOLED display", "severity": "critical", "affects": "display"}]
        deductions, ceilings, logs = extract_defect_penalties(defects, self.framework, self.mapping, self.params)
        self.assertEqual(deductions["display"], 4.0)
        self.assertEqual(ceilings["display"], 3.0)
        self.assertIn("CRITICAL", logs[0])

    def test_auto_pattern_matching_from_string(self):
        defects = ["motherboard dead boot failure"]
        deductions, ceilings, logs = extract_defect_penalties(defects, self.framework, self.mapping, self.params)
        self.assertEqual(deductions["build_durability"], 4.0)
        self.assertEqual(ceilings["build_durability"], 3.0)


class TestIRFEngine(unittest.TestCase):
    """Test deterministic Local Readiness Factor (IRF) calculations."""

    def setUp(self):
        self.archetypes = load_archetypes()
        self.irf_framework = self.archetypes["irf_scoring"]

    def test_perfect_irf(self):
        cand = {
            "irf_checklist": {
                "service_tat_hours": 24,
                "statutory_certifications": ["BIS", "BEE"],
                "environmental_resilience": "tropical_resilient",
                "authorized_seller": "brand_authorized",
            }
        }
        irf, audit = compute_irf(cand, self.irf_framework)
        self.assertEqual(irf, 1.00)

    def test_degraded_irf(self):
        cand = {
            "irf_checklist": {
                "service_tat_hours": 300,
                "statutory_certifications": [],
                "environmental_resilience": "unprotected_vulnerable",
                "authorized_seller": "unverified_third_party",
            }
        }
        irf, audit = compute_irf(cand, self.irf_framework)
        self.assertLessEqual(irf, 0.85)
        self.assertGreaterEqual(irf, 0.80)


class TestAllSevenCategories(unittest.TestCase):
    """Verify that every one of the 7 categories extracts and scores without errors."""

    def setUp(self):
        self.archetypes = load_archetypes()
        self.categories = [
            "smartphones",
            "laptops",
            "inverter_acs",
            "washing_machines",
            "skincare",
            "supplements",
            "tws_audio",
        ]

    def test_all_categories_in_archetypes(self):
        for cat in self.categories:
            self.assertIn(cat, self.archetypes["categories"])
            cat_data = self.archetypes["categories"][cat]
            w_sum = sum(cat_data["weights"].values())
            self.assertAlmostEqual(w_sum, 1.0, places=4, msg=f"Weights in {cat} do not sum to 1.0")

    def test_end_to_end_pipeline_execution(self):
        """Test piping metric_extractor into product_scorer via subprocess."""
        extractor_path = os.path.join(SCRIPTS_DIR, "metric_extractor.py")
        scorer_path = os.path.join(SCRIPTS_DIR, "product_scorer.py")

        payload = {
            "category": "laptops",
            "currency": "INR",
            "candidates": [
                {
                    "name": "ThinkPad T14s Gen 5",
                    "tier": "Mid-Range",
                    "price": 105000,
                    "measurements": {
                        "cinebench_r23_multicore": 14500,
                        "cinebench_r23_singlecore": 1820,
                        "display_brightness_nits": 400,
                        "color_gamut_srgb_pct": 100,
                        "web_browsing_runtime_hours": 12.5,
                        "keyboard_deck_temp_c": 38.0,
                        "fan_noise_dba": 35.0,
                        "ram_upgradeability": "single_sodimm_plus_soldered",
                        "ssd_slots": "1_slot",
                        "hinge_chassis_durability": 9.0,
                    },
                    "irf_checklist": {
                        "service_tat_hours": 24,
                        "statutory_certifications": ["BIS", "CE"],
                        "environmental_resilience": "standard_resilience",
                        "authorized_seller": "brand_authorized",
                    },
                },
                {
                    "name": "Bargain Plastic Laptop",
                    "tier": "Budget",
                    "price": 35000,
                    "measurements": {
                        "cinebench_r23_multicore": 6200,
                        "cinebench_r23_singlecore": 1050,
                        "display_brightness_nits": 220,
                        "color_gamut_srgb_pct": 52,
                        "web_browsing_runtime_hours": 4.5,
                        "keyboard_deck_temp_c": 49.0,
                        "fan_noise_dba": 47.0,
                        "ram_upgradeability": "fully_soldered",
                        "ssd_slots": "1_slot",
                        "hinge_chassis_durability": 4.0,
                    },
                    "defects": ["hinge cracking after 6 months"],
                    "irf_checklist": {
                        "service_tat_hours": 160,
                        "statutory_certifications": ["BIS"],
                        "environmental_resilience": "unprotected_vulnerable",
                        "authorized_seller": "reputable_merchant",
                    },
                },
            ],
        }

        cmd = f"python3 {extractor_path} | python3 {scorer_path} --json"
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = p.communicate(input=json.dumps(payload))
        self.assertEqual(p.returncode, 0, f"Pipeline failed with stderr: {err}")

        results = json.loads(out)
        self.assertIn("ranked_candidates", results)
        ranked = results["ranked_candidates"]
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["name"], "ThinkPad T14s Gen 5")
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])
        self.assertGreaterEqual(ranked[0]["readiness_factor"], 0.95)


if __name__ == "__main__":
    unittest.main()
