#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Wirecutter-Grade Defect Miner
Verifies defect taxonomy, severity classification, systemic vs batch vs lemon tagging,
negation filtering, lab measurement extraction, IRF checklist detection, dual output modes,
and end-to-end piping into metric_extractor.py and product_scorer.py.
"""

import json
import os
import subprocess
import sys
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from defect_miner import (
    CATEGORY_DEFECT_TAXONOMY,
    extract_defects_from_snippets,
    extract_measurements_from_text,
    extract_irf_from_text,
    extract_price_and_tier,
    demux_raw_input,
    mine_defects_and_metrics,
    format_as_extractor_json,
    format_as_wirecutter_markdown,
    candidate_in_snippet,
    parse_snippet_frequency,
)


class TestDefectTaxonomyAndSeverity(unittest.TestCase):
    """Test defect identification, severity categorization, and classification across categories."""

    def test_critical_defect_identification(self):
        snippets = [
            "User experienced motherboard dead boot failure after 4 months.",
            "Display green line after update appeared overnight.",
            "Refrigerant gas leak caused compressor dead failure.",
            "Drum spider arm galvanic corrosion fractured during spin cycle.",
            "Independent lab assay confirmed amino spiking with glycine.",
            "Earbud dead and unable to charge due to charging pin galvanic corrosion.",
        ]
        categories = ["smartphones", "smartphones", "inverter_acs", "washing_machines", "supplements", "tws_audio"]

        for snip, cat in zip(snippets, categories):
            defects = extract_defects_from_snippets(cat, [snip])
            self.assertGreater(len(defects), 0, f"Failed to detect defect in {cat}: {snip}")
            self.assertEqual(defects[0]["severity"], "critical", f"Defect should be critical in {cat}: {snip}")

    def test_severe_defect_identification(self):
        snippets = [
            "Laptop hinge cracking and chassis separation observed after 5 months.",
            "Extreme liquid metal pump-out led to severe thermal throttling.",
            "Persistent UE unbalanced load error and violent shaking during spin.",
            "Vitamin C turned dark brown rapid oxidation within 3 weeks.",
            "Piercing ANC feedback squeal high pitch whistle in left ear.",
        ]
        categories = ["laptops", "laptops", "washing_machines", "skincare", "tws_audio"]

        for snip, cat in zip(snippets, categories):
            defects = extract_defects_from_snippets(cat, [snip])
            self.assertGreater(len(defects), 0, f"Failed to detect defect in {cat}: {snip}")
            self.assertEqual(defects[0]["severity"], "severe", f"Defect should be severe in {cat}: {snip}")

    def test_moderate_and_minor_defects(self):
        # Moderate
        snip_mod = "Camera lens internal fogging in humidity noticed during winter."
        def_mod = extract_defects_from_snippets("smartphones", [snip_mod])
        self.assertEqual(def_mod[0]["severity"], "moderate")

        # Minor
        snip_minor = "The glossy back is a total fingerprint smudge magnet."
        def_minor = extract_defects_from_snippets("smartphones", [snip_minor])
        self.assertEqual(def_minor[0]["severity"], "minor")

    def test_defect_type_systemic_vs_batch_vs_lemon(self):
        # 1. Systemic design flaw (teardown / technician corroboration)
        teardown_snip = "Teardown by technician revealed galvanic corrosion of drum spider arm due to aluminium alloy."
        d_systemic = extract_defects_from_snippets("washing_machines", [teardown_snip])
        self.assertEqual(d_systemic[0]["defect_type"], "systemic_design_flaw")

        # 2. Batch defect (firmware / OTA / batch keywords with multiple users)
        batch_snip = "Five users reported vertical green line on display after software update batch 14.0.2."
        d_batch = extract_defects_from_snippets("smartphones", [batch_snip])
        self.assertIn(d_batch[0]["defect_type"], ["systemic_design_flaw", "batch_defect"])
        self.assertGreaterEqual(d_batch[0]["source_count"], 5)

        # 3. Isolated lemon (single report, no teardown or batch clue)
        lemon_snip = "My unit had a stiff volume button out of the box."
        d_lemon = extract_defects_from_snippets("smartphones", [lemon_snip])
        if d_lemon:
            self.assertEqual(d_lemon[0]["defect_type"], "isolated_lemon")

    def test_negation_filter_prevents_false_positives(self):
        clean_snippets = [
            "No green line or motherboard dead boot issues observed on this unit.",
            "Zero reports of compressor gas leak or outdoor PCB failure.",
            "Completely free from amino spiking or heavy metal contamination.",
            "Never had any hinge cracking or chassis separation problems.",
        ]
        cats = ["smartphones", "inverter_acs", "supplements", "laptops"]

        for snip, cat in zip(clean_snippets, cats):
            defects = extract_defects_from_snippets(cat, [snip])
            self.assertEqual(len(defects), 0, f"Negated statement should not trigger defect in {cat}: '{snip}'")


class TestLabMeasurementExtraction(unittest.TestCase):
    """Test regex extraction of physical lab measurements and discrete attributes."""

    def test_display_measurements(self):
        text = "Display reached peak brightness of 1600 nits with color accuracy Delta-E of 1.2 and 2160 Hz PWM dimming."
        m = extract_measurements_from_text(text)
        self.assertEqual(m.get("peak_brightness_nits"), 1600.0)
        self.assertEqual(m.get("color_accuracy_delta_e"), 1.2)
        self.assertEqual(m.get("pwm_dimming_hz"), 2160.0)

    def test_thermals_noise_and_performance(self):
        text = "Cinebench R23 multi: 14500, single: 1820. Peak temp: 42.5°C under load, keyboard deck temp: 38.0°C. Fan noise: 36.5 dBA, sustained performance: 88%."
        m = extract_measurements_from_text(text)
        self.assertEqual(m.get("cinebench_r23_multicore"), 14500.0)
        self.assertEqual(m.get("cinebench_r23_singlecore"), 1820.0)
        self.assertEqual(m.get("thermal_peak_temp_c"), 42.5)
        self.assertEqual(m.get("keyboard_deck_temp_c"), 38.0)
        self.assertEqual(m.get("fan_noise_dba"), 36.5)
        self.assertEqual(m.get("sustained_perf_percent"), 88.0)

    def test_battery_and_charging(self):
        text = "Battery runtime was 14.5 hours of web browsing. Battery capacity: 5000 mAh. 67W fast charging charges full in 35 mins."
        m = extract_measurements_from_text(text)
        self.assertEqual(m.get("active_battery_runtime_hours"), 14.5)
        self.assertEqual(m.get("battery_capacity_mah"), 5000.0)
        self.assertEqual(m.get("charging_wattage"), 67.0)
        self.assertEqual(m.get("charging_time_minutes"), 35.0)

    def test_air_conditioner_metrics(self):
        text = "Features 5.25 ISEER rating, 100% grooved copper condenser coil with ocean black protection. Indoor noise of 24 dB and outdoor compressor at 48 dB."
        m = extract_measurements_from_text(text)
        self.assertEqual(m.get("iseer_rating"), 5.25)
        self.assertEqual(m.get("coil_material"), "100%_grooved_copper")
        self.assertEqual(m.get("anti_corrosion_coating"), "ocean_black_gold_fin")
        self.assertEqual(m.get("indoor_silent_db"), 24.0)
        self.assertEqual(m.get("outdoor_compressor_db"), 48.0)

    def test_washing_machine_and_skincare_metrics(self):
        # Washing machine
        wm_text = "Direct drive motor, 1400 RPM spin speed, laser welded stainless steel drum, water consumption: 8.5 L/kg."
        m_wm = extract_measurements_from_text(wm_text)
        self.assertEqual(m_wm.get("motor_type"), "direct_drive_inverter")
        self.assertEqual(m_wm.get("max_spin_speed_rpm"), 1400.0)
        self.assertEqual(m_wm.get("drum_material"), "laser_welded_stainless_steel")
        self.assertEqual(m_wm.get("water_consumption_litres_per_kg"), 8.5)

        # Skincare
        sk_text = "Formulated with 10% Niacinamide in opaque airless pump bottle. Optical image stabilization: no."
        m_sk = extract_measurements_from_text(sk_text)
        self.assertEqual(m_sk.get("active_concentration_pct"), 10.0)
        self.assertEqual(m_sk.get("container_type"), "opaque_airless_pump")

    def test_audio_and_supplement_metrics(self):
        # Supplements
        supp_text = "Delivers 80% protein content and 24g protein per scoop. Zero amino spiking verified. Multi-enzyme DigeZyme included."
        m_supp = extract_measurements_from_text(supp_text)
        self.assertEqual(m_supp.get("protein_or_active_purity_pct"), 80.0)
        self.assertEqual(m_supp.get("active_yield_per_serving_g"), 24.0)
        self.assertTrue(m_supp.get("zero_amino_spiking_verified"))
        self.assertEqual(m_supp.get("digestive_enzyme_complex"), "multi_enzyme_digezyme")

        # TWS Audio
        tws_text = "ANC reduces 42 dB of ambient noise. 8 hours with ANC on, 32 hours with case. LDAC lossless audio support, IPX7 water rating."
        m_tws = extract_measurements_from_text(tws_text)
        self.assertEqual(m_tws.get("anc_noise_attenuation_db"), 42.0)
        self.assertEqual(m_tws.get("single_charge_anc_hours"), 8.0)
        self.assertEqual(m_tws.get("total_case_hours"), 32.0)
        self.assertEqual(m_tws.get("hi_res_codec_support"), "ldac_lhdc_lossless")
        self.assertEqual(m_tws.get("ip_water_rating"), "ipx7")


class TestIRFAttributeDetection(unittest.TestCase):
    """Test Local Readiness Factor (IRF) checklist extraction."""

    def test_service_tat_extraction(self):
        text_hours = "Service TAT of 36 hours across tier-1 cities."
        irf_hours = extract_irf_from_text(text_hours)
        self.assertEqual(irf_hours.get("service_tat_hours"), 36)

        text_days = "Product repaired in 3 days under warranty."
        irf_days = extract_irf_from_text(text_days)
        self.assertEqual(irf_days.get("service_tat_days"), 3)
        self.assertEqual(irf_days.get("service_tat_hours"), 72)

    def test_statutory_certifications(self):
        text = "Certified with BIS CRS mark, BEE 5-Star ISEER, and CE European compliance."
        irf = extract_irf_from_text(text)
        self.assertIn("BIS", irf.get("statutory_certifications", []))
        self.assertIn("BEE", irf.get("statutory_certifications", []))
        self.assertIn("CE", irf.get("statutory_certifications", []))

    def test_environmental_and_channel_legitimacy(self):
        text = "Equipped with tropical 52°C ambient cooling and gold fin anti-corrosion. Sold via official brand store."
        irf = extract_irf_from_text(text)
        self.assertEqual(irf.get("environmental_resilience"), "tropical_resilient")
        self.assertEqual(irf.get("authorized_seller"), "brand_authorized")


class TestDualOutputModes(unittest.TestCase):
    """Test JSON output schema compatibility and Wirecutter Markdown generation."""

    def setUp(self):
        self.sample_text = """
        # ThinkPad T14s Gen 5
        Cinebench R23 multi: 14500, single: 1820. Display brightness: 400 nits, Delta-E: 1.2.
        Web browsing runtime: 12.5 hours. Keyboard deck temp: 38°C, fan noise: 35 dBA.
        Dual SODIMM ram upgradeability, 2x M.2 ssd slots.
        No hinge cracking or liquid metal pump-out issues.
        Service TAT 24 hours at brand authorized store. BIS and CE certified. Price: 105000.
        """

    def test_to_extractor_json_schema(self):
        mined = mine_defects_and_metrics(self.sample_text, category="laptops")
        json_str = format_as_extractor_json(mined)
        data = json.loads(json_str)

        self.assertEqual(data["category"], "laptops")
        self.assertIn("candidates", data)
        self.assertEqual(len(data["candidates"]), 1)

        cand = data["candidates"][0]
        self.assertEqual(cand["name"], "ThinkPad T14s Gen 5")
        self.assertEqual(cand["price"], 105000.0)
        self.assertIn("measurements", cand)
        self.assertIn("defects", cand)
        self.assertIn("irf_checklist", cand)
        self.assertEqual(cand["measurements"]["cinebench_r23_multicore"], 14500.0)
        self.assertEqual(cand["irf_checklist"]["service_tat_hours"], 24)

    def test_markdown_wirecutter_audit_structure(self):
        mined = mine_defects_and_metrics(self.sample_text, category="laptops")
        md = format_as_wirecutter_markdown(mined)

        self.assertIn("## Wirecutter-Grade Defect & Longevity Audit: Laptops", md)
        self.assertIn("Methodology Bar:", md)
        self.assertIn("Comparative Defect & Failure Mode Taxonomy", md)
        self.assertIn("Harvested Lab Benchmarks & Physical Measurements", md)
        self.assertIn("Local Ecosystem & Readiness (IRF) Verification", md)
        self.assertIn("ThinkPad T14s Gen 5", md)


class TestEndToEndSubprocessPipeline(unittest.TestCase):
    """Test full piping: defect_miner -> metric_extractor -> product_scorer."""

    def test_full_pipe_smartphones(self):
        input_data = [
            {
                "title": "OnePlus 12 Long-Term Review",
                "snippet": "OnePlus 12 reached 1600 nits peak brightness, Delta-E 1.3, 14.5 hours active battery life. 4 users reported camera lens internal fogging in humidity. Multiple users experienced vertical green line on display after update. Service TAT 36 hours. BIS and CE certified. Tropical resilient cooling. Price: 64999.",
            },
            {
                "title": "Samsung Galaxy S24 Reliability Review",
                "snippet": "Galaxy S24 measured 1450 nits brightness, Delta-E 1.1, 13 hours battery. Zero green line or motherboard dead boot issues observed. Minor complaint about fingerprint smudge magnet. Service TAT 24 hours at authorized brand store. BIS and CE certified. Aluminum frame. Price: 79999.",
            },
        ]

        miner_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'defect_miner.py')} --category smartphones --candidates 'OnePlus 12, Samsung Galaxy S24' --to-extractor-json"
        extractor_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'metric_extractor.py')}"
        scorer_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'product_scorer.py')} --json"

        full_cmd = f"{miner_cmd} | {extractor_cmd} | {scorer_cmd}"

        p = subprocess.Popen(
            full_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(input=json.dumps(input_data))

        self.assertEqual(p.returncode, 0, f"Pipeline failed with stderr: {stderr}")
        results = json.loads(stdout)

        self.assertIn("ranked_candidates", results)
        ranked = results["ranked_candidates"]
        self.assertEqual(len(ranked), 2)

        # Samsung S24 should rank #1 due to clean reliability vs OnePlus 12 green line penalty clamp
        self.assertEqual(ranked[0]["name"], "Samsung Galaxy S24")
        self.assertEqual(ranked[1]["name"], "OnePlus 12")
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])

        # OnePlus 12 has lower price and higher VFM
        self.assertGreater(ranked[1]["vfm_index"], ranked[0]["vfm_index"])

    def test_full_pipe_inverter_acs(self):
        input_data = [
            {
                "title": "Daikin FTKM50 1.5T Review",
                "snippet": "Daikin achieved 5.2 ISEER rating, 100% grooved copper coil with gold fin anti-corrosion. Silent 24 dB IDU noise and 46 dB outdoor compressor. Zero reports of refrigerant gas leak. Service TAT 24 hours. Certified BEE and BIS. Price: 48000.",
            },
            {
                "title": "Budget Aluminium AC Warning",
                "snippet": "Budget AC measured 3.8 ISEER rating, aluminium coil with no coating. Indoor unit noise was 36 dB. Multiple complaints regarding refrigerant gas leak and outdoor PCB failure after power surge. Service TAT 12 days. Price: 26000.",
            },
        ]

        miner_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'defect_miner.py')} --category inverter_acs --candidates 'Daikin FTKM50, Budget Aluminium AC' --to-extractor-json"
        extractor_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'metric_extractor.py')}"
        scorer_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'product_scorer.py')} --json"

        full_cmd = f"{miner_cmd} | {extractor_cmd} | {scorer_cmd}"

        p = subprocess.Popen(
            full_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(input=json.dumps(input_data))
        self.assertEqual(p.returncode, 0, f"AC Pipeline failed with stderr: {stderr}")

        results = json.loads(stdout)
        self.assertIn("ranked_candidates", results)
        ranked = results["ranked_candidates"]
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["name"], "Daikin FTKM50")
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])

    def test_full_pipe_washing_machines(self):
        input_data = [
            {
                "title": "Bosch Series 6 Front Load Review",
                "snippet": "Bosch Series 6 features 1400 RPM spin speed, direct drive inverter motor, and laser welded stainless steel drum. Water consumption: 8.2 L/kg. Zero spider arm corrosion or tub bearing leaks observed. Service TAT 24 hours. BEE 5-star and BIS certified. Price: 38999.",
            },
            {
                "title": "Unbranded Top Load Washing Machine",
                "snippet": "Top load machine spins at 700 RPM, plastic drum. Violent vibration during spin and drum spider arm corrosion reported by multiple owners on forum. Service TAT took 14 days for technician visit. Price: 15000.",
            },
        ]

        miner_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'defect_miner.py')} --category washing_machines --candidates 'Bosch Series 6, Unbranded Top Load' --to-extractor-json"
        extractor_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'metric_extractor.py')}"
        scorer_cmd = f"python3 {os.path.join(SCRIPTS_DIR, 'product_scorer.py')} --json"

        full_cmd = f"{miner_cmd} | {extractor_cmd} | {scorer_cmd}"

        p = subprocess.Popen(
            full_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = p.communicate(input=json.dumps(input_data))
        self.assertEqual(p.returncode, 0, f"Washing machine Pipeline failed with stderr: {stderr}")

        results = json.loads(stdout)
        ranked = results["ranked_candidates"]
        self.assertEqual(ranked[0]["name"], "Bosch Series 6")
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])

    def test_cli_flags_and_file_io(self):
        """Test -o output flag and --text flag directly."""
        tmp_out = "/tmp/test_miner_output.json"
        text = "ThinkPad T14s achieved 14500 Cinebench R23 multi and 400 nits. No hinge cracking. Service TAT 24 hours. Price: 105000."
        cmd = [
            "python3",
            os.path.join(SCRIPTS_DIR, "defect_miner.py"),
            "--text",
            text,
            "-c",
            "laptops",
            "--to-extractor-json",
            "-o",
            tmp_out,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.isfile(tmp_out))

        with open(tmp_out, "r") as f:
            data = json.load(f)
        self.assertEqual(data["category"], "laptops")
        self.assertEqual(len(data["candidates"]), 1)
        os.remove(tmp_out)


if __name__ == "__main__":
    unittest.main()
