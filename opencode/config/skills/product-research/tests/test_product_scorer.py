#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Product Scorer CLI
Verifies Data Confidence Tracking, Imputed Data Uncertainty Penalties,
Automated Sensitivity & Perturbation Engine (Monte Carlo Rank Stability),
Exact Parameter/Weight/Price Flipping Thresholds, and full 3-stage pipeline execution:
defect_miner.py -> metric_extractor.py -> product_scorer.py
"""

import json
import os
import subprocess
import sys
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from product_scorer import (
    compute_candidate_confidence,
    compute_flipping_thresholds,
    compute_price_elasticity,
    format_currency,
    load_archetypes,
    normalize_weights,
    render_markdown,
    score_candidates,
)


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence score derivation, tier assignment, flags, and uncertainty penalties."""

    def setUp(self):
        self.weights = {
            "performance": 0.25,
            "display": 0.15,
            "camera": 0.20,
            "battery_charging": 0.15,
            "build_durability": 0.10,
            "software_support": 0.15,
        }
        self.archetypes = load_archetypes()

    def test_confidence_explicit_numeric(self):
        # 0.95 -> 95%, HIGH tier, zero penalty
        cand_high = {"name": "Lab Tested Phone", "confidence": 0.95}
        score, tier, flag, pen = compute_candidate_confidence(cand_high, self.weights, self.archetypes, "smartphones")
        self.assertEqual(score, 95.0)
        self.assertIn("HIGH", tier)
        self.assertEqual(flag, "HIGH")
        self.assertEqual(pen, 0.0)

        # 0.65 -> 65%, MEDIUM tier, moderate penalty
        cand_med = {"name": "Spec Corroborated Phone", "confidence": 0.65}
        score, tier, flag, pen = compute_candidate_confidence(cand_med, self.weights, self.archetypes, "smartphones")
        self.assertEqual(score, 65.0)
        self.assertIn("MEDIUM", tier)
        self.assertEqual(flag, "MED")
        self.assertGreater(pen, 0.0)
        self.assertLessEqual(pen, 0.10)

        # 0.30 -> 30%, LOW tier, severe penalty
        cand_low = {"name": "Unverified Phone", "confidence": 0.30}
        score, tier, flag, pen = compute_candidate_confidence(cand_low, self.weights, self.archetypes, "smartphones")
        self.assertEqual(score, 30.0)
        self.assertIn("LOW", tier)
        self.assertEqual(flag, "⚠️ LOW")
        self.assertGreaterEqual(pen, 0.15)

    def test_confidence_explicit_string(self):
        cand_high = {"name": "Device A", "confidence": "HIGH (Lab Tested)"}
        score, tier, flag, pen = compute_candidate_confidence(cand_high, self.weights, self.archetypes, "smartphones")
        self.assertGreaterEqual(score, 80.0)
        self.assertIn("HIGH", tier)

        cand_low = {"name": "Device B", "confidence": "LOW"}
        score, tier, flag, pen = compute_candidate_confidence(cand_low, self.weights, self.archetypes, "smartphones")
        self.assertLess(score, 50.0)
        self.assertIn("LOW", tier)
        self.assertEqual(flag, "⚠️ LOW")

    def test_confidence_from_verified_parameters(self):
        # 2 of 6 parameters verified -> 40% weighted
        cand = {"name": "Partial Device", "verified_parameters": ["performance", "display"]}
        score, tier, flag, pen = compute_candidate_confidence(cand, self.weights, self.archetypes, "smartphones")
        self.assertAlmostEqual(score, 40.0, places=1)
        self.assertIn("LOW", tier)
        self.assertGreater(pen, 0.10)

        # 5 of 6 parameters verified -> 90% weighted
        cand_rich = {
            "name": "Thorough Device",
            "verified_parameters": ["performance", "display", "camera", "battery_charging", "software_support"],
        }
        score, tier, flag, pen = compute_candidate_confidence(cand_rich, self.weights, self.archetypes, "smartphones")
        self.assertAlmostEqual(score, 90.0, places=1)
        self.assertIn("HIGH", tier)
        self.assertEqual(pen, 0.0)

    def test_confidence_from_evidence_count(self):
        cand = {"name": "Evidence Device", "evidence_count": 6}
        score, tier, flag, pen = compute_candidate_confidence(cand, self.weights, self.archetypes, "smartphones")
        self.assertEqual(score, 100.0)
        self.assertIn("HIGH", tier)

        cand_sparse = {"name": "Sparse Device", "evidence_count": 1}
        score, tier, flag, pen = compute_candidate_confidence(cand_sparse, self.weights, self.archetypes, "smartphones")
        self.assertLess(score, 50.0)
        self.assertIn("LOW", tier)

    def test_confidence_from_extraction_audit(self):
        audit_lab = {
            "parameter_breakdown": {
                p: {"derived_from_lab_measurements": True, "source": "lab"}
                for p in self.weights
            }
        }
        cand_lab = {"name": "Lab Device", "extraction_audit": audit_lab}
        score, tier, flag, pen = compute_candidate_confidence(cand_lab, self.weights, self.archetypes, "smartphones")
        self.assertEqual(score, 100.0)
        self.assertIn("HIGH", tier)
        self.assertEqual(pen, 0.0)

        audit_imputed = {
            "parameter_breakdown": {
                p: {"derived_from_lab_measurements": False, "source": "category_neutral_baseline"}
                for p in self.weights
            }
        }
        cand_imputed = {"name": "Imputed Device", "extraction_audit": audit_imputed}
        score, tier, flag, pen = compute_candidate_confidence(cand_imputed, self.weights, self.archetypes, "smartphones")
        self.assertEqual(score, 0.0)
        self.assertIn("LOW", tier)
        self.assertEqual(flag, "⚠️ LOW")
        self.assertGreaterEqual(pen, 0.30)

    def test_unverified_candidate_cannot_outrank_verified_candidate(self):
        """
        Prevent an unverified candidate with missing data / default baseline
        from outranking a fully lab-tested candidate.
        """
        data = {
            "category": "smartphones",
            "currency": "INR",
            "candidates": [
                {
                    "name": "Fully Tested Contender",
                    "tier": "Mid-Range",
                    "price": 50000,
                    "confidence": 0.95,
                    "readiness_factor": 1.0,
                    "scores": {
                        "performance": 8.2,
                        "display": 8.0,
                        "camera": 8.0,
                        "battery_charging": 8.0,
                        "build_durability": 8.0,
                        "software_support": 8.0,
                    },
                },
                {
                    "name": "Unverified Marketing Claims",
                    "tier": "Mid-Range",
                    "price": 50000,
                    "confidence": 0.20,  # LOW tier (missing lab tests, imputed defaults)
                    "readiness_factor": 1.0,
                    "scores": {
                        "performance": 8.6,
                        "display": 8.5,
                        "camera": 8.5,
                        "battery_charging": 8.5,
                        "build_durability": 8.5,
                        "software_support": 8.5,
                    },
                },
            ],
        }

        results = score_candidates(data, self.archetypes)
        ranked = results["ranked_candidates"]

        # Verified contender must rank #1 despite lower nominal raw score
        self.assertEqual(ranked[0]["name"], "Fully Tested Contender")
        self.assertEqual(ranked[1]["name"], "Unverified Marketing Claims")
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])
        self.assertIn("HIGH", ranked[0]["confidence_tier"])
        self.assertIn("LOW", ranked[1]["confidence_tier"])
        self.assertEqual(ranked[1]["confidence_flag"], "⚠️ LOW")

    def test_markdown_flags_low_confidence(self):
        data = {
            "category": "smartphones",
            "currency": "INR",
            "candidates": [
                {
                    "name": "Verified Pro",
                    "tier": "Flagship",
                    "price": 79999,
                    "confidence": 0.90,
                    "scores": {p: 8.5 for p in self.weights},
                },
                {
                    "name": "Shady Clone",
                    "tier": "Budget",
                    "price": 19999,
                    "confidence": 0.25,
                    "scores": {p: 7.0 for p in self.weights},
                },
            ],
        }
        results = score_candidates(data, self.archetypes)
        md = render_markdown(results)

        self.assertIn("⚠️ LOW (25%)", md)
        self.assertIn("HIGH (90%)", md)
        self.assertIn("Data Confidence Alert", md)


class TestSensitivityAndRankStability(unittest.TestCase):
    """Test Monte Carlo weight perturbation and candidate rank stability calculation."""

    def setUp(self):
        self.archetypes = load_archetypes()

    def test_monte_carlo_rank_stability_clear_winner(self):
        data = {
            "category": "laptops",
            "currency": "USD",
            "candidates": [
                {
                    "name": "Dominant Workstation",
                    "tier": "Flagship",
                    "price": 2500,
                    "confidence": 0.95,
                    "readiness_factor": 1.0,
                    "scores": {
                        "performance": 9.8,
                        "display_accuracy": 9.5,
                        "battery_life": 9.0,
                        "cooling_thermals": 9.2,
                        "build_upgradeability": 9.0,
                    },
                },
                {
                    "name": "Mediocre Ultraportable",
                    "tier": "Budget",
                    "price": 900,
                    "confidence": 0.90,
                    "readiness_factor": 0.90,
                    "scores": {
                        "performance": 6.0,
                        "display_accuracy": 5.5,
                        "battery_life": 6.0,
                        "cooling_thermals": 5.0,
                        "build_upgradeability": 5.0,
                    },
                },
            ],
        }

        results = score_candidates(data, self.archetypes, mc_iterations=100, seed=42)
        ranked = results["ranked_candidates"]
        winner = ranked[0]

        self.assertEqual(winner["name"], "Dominant Workstation")
        self.assertEqual(winner["rank_stability_pct"], 100.0)
        self.assertEqual(winner["stability_tier"], "Solid")

        sens = results["sensitivity_analysis"]
        self.assertEqual(sens["winner_robustness"]["winner_name"], "Dominant Workstation")
        self.assertEqual(sens["winner_robustness"]["stability_pct"], 100.0)
        self.assertEqual(sens["winner_robustness"]["robustness_tier"], "ROBUST (Solid Winner)")

    def test_monte_carlo_fragile_pick(self):
        data = {
            "category": "generic",
            "currency": "USD",
            "weights": {"param_a": 0.50, "param_b": 0.50},
            "candidates": [
                {
                    "name": "Candidate A",
                    "price": 1000,
                    "confidence": 0.90,
                    "scores": {"param_a": 8.2, "param_b": 7.8},
                },
                {
                    "name": "Candidate B",
                    "price": 1000,
                    "confidence": 0.90,
                    "scores": {"param_a": 7.7, "param_b": 8.25},
                },
            ],
        }

        results = score_candidates(data, self.archetypes, mc_iterations=100, seed=42)
        ranked = results["ranked_candidates"]
        winner = ranked[0]

        self.assertLess(winner["rank_stability_pct"], 90.0)
        self.assertIn(winner["stability_tier"], ("Stable", "Fragile"))

    def test_deterministic_reproducibility(self):
        data = {
            "category": "smartphones",
            "currency": "INR",
            "candidates": [
                {"name": "Phone 1", "price": 40000, "confidence": 0.9, "scores": {"performance": 8.5, "camera": 7.5, "display": 8.0, "battery_charging": 8.0, "build_durability": 8.0, "software_support": 8.0}},
                {"name": "Phone 2", "price": 42000, "confidence": 0.9, "scores": {"performance": 8.0, "camera": 8.4, "display": 8.2, "battery_charging": 7.8, "build_durability": 8.0, "software_support": 7.8}},
            ],
        }
        res1 = score_candidates(data, self.archetypes, mc_iterations=50, seed=123)
        res2 = score_candidates(data, self.archetypes, mc_iterations=50, seed=123)

        stab1 = res1["ranked_candidates"][0]["rank_stability_pct"]
        stab2 = res2["ranked_candidates"][0]["rank_stability_pct"]
        self.assertEqual(stab1, stab2)


class TestFlippingThresholds(unittest.TestCase):
    """Test exact parameter score, priority weight, and price discount flipping thresholds."""

    def setUp(self):
        self.archetypes = load_archetypes()
        self.weights = {
            "performance": 0.25,
            "display": 0.15,
            "camera": 0.20,
            "battery_charging": 0.15,
            "build_durability": 0.10,
            "software_support": 0.15,
        }

    def test_exact_parameter_delta_threshold(self):
        data = {
            "category": "smartphones",
            "currency": "INR",
            "candidates": [
                {
                    "name": "Leader Phone",
                    "price": 60000,
                    "confidence": 1.0,
                    "readiness_factor": 1.0,
                    "scores": {"performance": 8.5, "display": 8.0, "camera": 8.0, "battery_charging": 8.0, "build_durability": 8.0, "software_support": 8.0},
                },
                {
                    "name": "Challenger Phone",
                    "price": 55000,
                    "confidence": 1.0,
                    "readiness_factor": 1.0,
                    "scores": {"performance": 8.0, "display": 8.0, "camera": 8.0, "battery_charging": 8.0, "build_durability": 8.0, "software_support": 8.0},
                },
            ],
        }

        results = score_candidates(data, self.archetypes)
        flips = results["sensitivity_analysis"]["flipping_thresholds"]

        self.assertEqual(flips["leader"], "Leader Phone")
        self.assertEqual(flips["challenger"], "Challenger Phone")
        gap = flips["score_gap"]
        self.assertGreater(gap, 0.0)

        cam_delta = flips["parameter_deltas"]["camera"]
        expected_delta = round(gap / (0.20 * 1.0), 2)
        self.assertAlmostEqual(cam_delta["delta_required"], expected_delta, places=2)
        self.assertTrue(cam_delta["achievable"])
        self.assertLessEqual(cam_delta["target_score"], 10.0)

    def test_exact_weight_delta_threshold(self):
        # Performance King has higher score (leader). Camera Specialist is Challenger with Camera strength.
        data = {
            "category": "smartphones",
            "currency": "INR",
            "candidates": [
                {
                    "name": "Performance King",
                    "price": 60000,
                    "confidence": 1.0,
                    "readiness_factor": 1.0,
                    "scores": {"performance": 9.8, "display": 8.0, "camera": 7.0, "battery_charging": 8.0, "build_durability": 8.0, "software_support": 8.0},
                },
                {
                    "name": "Camera Specialist",
                    "price": 60000,
                    "confidence": 1.0,
                    "readiness_factor": 1.0,
                    "scores": {"performance": 8.0, "display": 8.0, "camera": 9.0, "battery_charging": 8.0, "build_durability": 8.0, "software_support": 8.0},
                },
            ],
        }

        results = score_candidates(data, self.archetypes)
        flips = results["sensitivity_analysis"]["flipping_thresholds"]

        self.assertEqual(flips["leader"], "Performance King")
        self.assertEqual(flips["challenger"], "Camera Specialist")

        # Camera weight increase should be identified as viable path for Camera Specialist to flip
        cam_w = flips["weight_deltas"]["camera"]
        self.assertTrue(cam_w["achievable"])
        self.assertGreater(cam_w["weight_delta_required"], 0.0)
        self.assertLessEqual(cam_w["target_weight"], 1.0)

        # Verification: plugging in new camera weight flips or ties the winner
        new_w = dict(self.weights)
        new_w["camera"] = cam_w["target_weight"]
        for k in new_w:
            if k != "camera":
                new_w[k] = self.weights[k] * (1.0 - new_w["camera"]) / (1.0 - self.weights["camera"])

        data_flipped = dict(data)
        data_flipped["weights"] = new_w
        res_flipped = score_candidates(data_flipped, self.archetypes)
        c_cam = next(c for c in res_flipped["ranked_candidates"] if c["name"] == "Camera Specialist")
        c_perf = next(c for c in res_flipped["ranked_candidates"] if c["name"] == "Performance King")
        self.assertGreaterEqual(c_cam["final_score"], c_perf["final_score"] - 0.01)

    def test_price_vfm_threshold(self):
        data = {
            "category": "laptops",
            "currency": "INR",
            "candidates": [
                {"name": "Leader Laptop", "price": 100000, "confidence": 1.0, "scores": {"performance": 9.0, "display_accuracy": 8.5, "battery_life": 8.5, "cooling_thermals": 8.0, "build_upgradeability": 8.5}},
                {"name": "Challenger Laptop", "price": 100000, "confidence": 1.0, "scores": {"performance": 8.0, "display_accuracy": 8.0, "battery_life": 8.0, "cooling_thermals": 8.0, "build_upgradeability": 8.0}},
            ],
        }

        results = score_candidates(data, self.archetypes)
        flips = results["sensitivity_analysis"]["flipping_thresholds"]
        vfm_flip = flips["price_vfm_threshold"]

        self.assertEqual(vfm_flip["status"], "leader_leads")
        self.assertGreater(vfm_flip["discount_required_for_challenger"], 0.0)
        self.assertGreater(vfm_flip["discount_pct"], 0.0)

        target_p = vfm_flip["target_price"]
        chall_score = results["ranked_candidates"][1]["final_score"]
        leader_vfm = results["ranked_candidates"][0]["vfm_index"]
        chall_vfm_at_target = (chall_score / (target_p / 1000.0)) * 100.0
        self.assertGreaterEqual(chall_vfm_at_target, leader_vfm - 0.05)

    def test_single_candidate_no_challenger(self):
        data = {
            "category": "smartphones",
            "currency": "USD",
            "candidates": [{"name": "Solo Phone", "price": 800, "confidence": 0.9, "scores": {"performance": 8.0}}],
        }
        results = score_candidates(data, self.archetypes)
        flips = results["sensitivity_analysis"]["flipping_thresholds"]
        self.assertIn("message", flips)


class TestPriceElasticity(unittest.TestCase):
    """Test 5%, 10%, and 15% instant card discount price elasticity analysis."""

    def test_card_discounts(self):
        cand = [
            {"name": "Phone X", "price": 100000.0, "final_score": 8.0, "vfm_index": 8.0}
        ]
        res = compute_price_elasticity(cand, "INR")
        discounts = res["Phone X"]

        self.assertEqual(len(discounts), 3)
        self.assertEqual(discounts[0]["discount_pct"], 5)
        self.assertEqual(discounts[0]["discounted_price"], 95000.0)
        self.assertEqual(discounts[0]["discounted_price_formatted"], "₹95,000")
        self.assertAlmostEqual(discounts[0]["vfm_index"], 8.42, places=2)

        self.assertEqual(discounts[1]["discount_pct"], 10)
        self.assertEqual(discounts[1]["discounted_price"], 90000.0)
        self.assertAlmostEqual(discounts[1]["vfm_index"], 8.89, places=2)

        self.assertEqual(discounts[2]["discount_pct"], 15)
        self.assertEqual(discounts[2]["discounted_price"], 85000.0)
        self.assertAlmostEqual(discounts[2]["vfm_index"], 9.41, places=2)


class TestFullThreeStagePipeline(unittest.TestCase):
    """
    Integration Tests verifying the end-to-end 3-stage pipe:
    defect_miner.py -> metric_extractor.py -> product_scorer.py
    """

    def test_three_stage_pipeline_smartphones(self):
        input_data = [
            {
                "title": "OnePlus 12 Detailed Lab Review",
                "snippet": "OnePlus 12 measured 1600 nits peak brightness, Delta-E: 1.2, Geekbench 6: 6800, sustained performance: 85%, 40°C surface temp, 14.5 hours active battery, full charge in 26 mins. 4 users reported camera lens fogging in humidity. Service TAT 36 hours. BIS and CE certified. Price: 64999.",
            },
            {
                "title": "Samsung Galaxy S24 Ultra Lab Review",
                "snippet": "Galaxy S24 Ultra achieved 1500 nits brightness, Delta-E: 1.0, Geekbench 6: 7100, sustained performance: 88%, 39°C surface temp, 15.0 hours active battery, full charge in 32 mins. Zero motherboard issues. Service TAT 24 hours. BIS certified. Price: 89999.",
            },
        ]

        miner_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'defect_miner.py')} --category smartphones --candidates 'OnePlus 12, Samsung Galaxy S24 Ultra' --to-extractor-json"
        extractor_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'metric_extractor.py')}"
        scorer_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'product_scorer.py')} --json"

        pipe_cmd = f"{miner_cmd} | {extractor_cmd} | {scorer_cmd}"
        p = subprocess.Popen(
            pipe_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(input=json.dumps(input_data))

        self.assertEqual(p.returncode, 0, f"3-stage pipeline failed: {stderr}")
        results = json.loads(stdout)

        self.assertIn("ranked_candidates", results)
        self.assertIn("sensitivity_analysis", results)
        self.assertEqual(len(results["ranked_candidates"]), 2)

        for cand in results["ranked_candidates"]:
            self.assertIn("confidence_score", cand)
            self.assertIn("confidence_tier", cand)
            self.assertIn("rank_stability_pct", cand)
            self.assertIn("stability_tier", cand)
            self.assertIn("price_sensitivity", cand)
            self.assertGreaterEqual(cand["confidence_score"], 50.0)

        sens = results["sensitivity_analysis"]
        self.assertIn("winner_robustness", sens)
        self.assertIn("candidate_stability", sens)
        self.assertIn("flipping_thresholds", sens)
        self.assertIn("price_elasticity", sens)

    def test_three_stage_pipeline_markdown_output(self):
        input_data = [
            {
                "title": "Daikin FTKM50 Inverter AC Review",
                "snippet": "Daikin FTKM50 recorded 5.2 ISEER rating, 100% grooved copper coil with gold fin. 24 dB indoor silent noise, 46 dB compressor noise. Zero refrigerant gas leak. Service TAT 24 hours. BEE 5-star, BIS certified. Price: 48000.",
            },
            {
                "title": "Cheap AC Warning",
                "snippet": "Cheap AC recorded 3.7 ISEER rating, aluminium coil. Indoor noise was 36 dB. Multiple refrigerant gas leak reports. Service TAT 12 days. Price: 26000.",
            },
        ]

        miner_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'defect_miner.py')} --category inverter_acs --candidates 'Daikin FTKM50, Cheap AC' --to-extractor-json"
        extractor_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'metric_extractor.py')}"
        scorer_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'product_scorer.py')} --markdown"

        pipe_cmd = f"{miner_cmd} | {extractor_cmd} | {scorer_cmd}"
        p = subprocess.Popen(
            pipe_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(input=json.dumps(input_data))

        self.assertEqual(p.returncode, 0, f"Markdown 3-stage pipe failed: {stderr}")

        self.assertIn("Confidence", stdout)
        self.assertIn("Stability", stdout)
        self.assertIn("Sensitivity & Rank Stability Audit", stdout)
        self.assertIn("Winner Robustness", stdout)
        self.assertIn("Nearest Challenger Flipping Thresholds", stdout)
        self.assertIn("Price Elasticity & Discount Sensitivity", stdout)

    def test_three_stage_pipeline_unverified_prevention(self):
        """
        Verify that an unverified candidate with missing data passed into the pipeline
        is flagged as LOW confidence and penalized so it cannot outrank the lab-tested product.
        """
        input_data = [
            {
                "title": "Bosch Series 6 Lab Review",
                "snippet": "Bosch Series 6 features 1400 RPM spin speed, direct drive motor, laser welded stainless steel drum, spin noise 52 dB. Water consumption: 8.0 L/kg. Zero spider arm corrosion. Service TAT 24 hours. BEE 5-star, BIS certified. Price: 38000.",
            },
            {
                "title": "Vague Washer Overview",
                "snippet": "Vague Washer is advertised online for general laundry. No lab tests conducted. Price: 38000.",
            },
        ]

        miner_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'defect_miner.py')} --category washing_machines --candidates 'Bosch Series 6, Vague Washer' --to-extractor-json"
        extractor_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'metric_extractor.py')}"
        scorer_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'product_scorer.py')} --json"

        pipe_cmd = f"{miner_cmd} | {extractor_cmd} | {scorer_cmd}"
        p = subprocess.Popen(
            pipe_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(input=json.dumps(input_data))

        self.assertEqual(p.returncode, 0, f"Pipeline failed: {stderr}")
        results = json.loads(stdout)
        ranked = results["ranked_candidates"]

        self.assertEqual(ranked[0]["name"], "Bosch Series 6")
        self.assertEqual(ranked[1]["name"], "Vague Washer")
        self.assertIn("HIGH", ranked[0]["confidence_tier"])
        self.assertIn("LOW", ranked[1]["confidence_tier"])
        self.assertEqual(ranked[1]["confidence_flag"], "⚠️ LOW")
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])


if __name__ == "__main__":
    unittest.main()
