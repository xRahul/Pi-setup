#!/usr/bin/env python3
"""
Metric Extractor & Normalization Engine CLI
Bridges raw lab measurements, test numbers, and defect findings into normalized
0–10 parameter scores and a calibrated 0.80–1.00 Local Readiness Factor (IRF).

Supported inputs:
  - Numerical lab measurements (peak nits, sustained Geekbench/Cinebench scores,
    dBA noise levels, Delta-E color error, ISEER rating, active % wt/vol, etc.)
    mapped through RTINGS-grade piecewise linear, discrete, or sigmoid curves.
  - Defect & reliability findings: deducts calibrated penalty points for confirmed
    severe defects (dead motherboard, green lines, compressor leaks, amino spiking)
    vs minor cosmetic bugs, with max parameter score ceilings.
  - IRF checklist: computes exact IRF (0.80 to 1.00) deterministically from verified
    service TAT, statutory certification, environmental resilience, and seller channel.

Directly pipes into product_scorer.py:
  python3 scripts/metric_extractor.py --input raw_data.json | python3 scripts/product_scorer.py --markdown
"""

import argparse
import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Common measurement aliases for resilient fuzzy extraction
MEASUREMENT_ALIASES: Dict[str, str] = {
    # Display
    "nits": "peak_brightness_nits",
    "brightness": "peak_brightness_nits",
    "peak_nits": "peak_brightness_nits",
    "brightness_nits": "peak_brightness_nits",
    "display_brightness": "display_brightness_nits",
    "delta_e": "color_accuracy_delta_e",
    "deltae": "color_accuracy_delta_e",
    "color_delta_e": "color_accuracy_delta_e",
    "pwm": "pwm_dimming_hz",
    "pwm_hz": "pwm_dimming_hz",
    "flicker_hz": "pwm_dimming_hz",
    "srgb": "color_gamut_srgb_pct",
    "srgb_pct": "color_gamut_srgb_pct",
    "srgb_coverage": "color_gamut_srgb_pct",
    # Compute / Thermals
    "geekbench": "geekbench_multicore",
    "geekbench6": "geekbench_multicore",
    "gb6_multi": "geekbench_multicore",
    "gb_multi": "geekbench_multicore",
    "cinebench": "cinebench_r23_multicore",
    "cb_r23_multi": "cinebench_r23_multicore",
    "cinebench_multi": "cinebench_r23_multicore",
    "cb_r23_single": "cinebench_r23_singlecore",
    "cinebench_single": "cinebench_r23_singlecore",
    "sustained_perf": "sustained_perf_percent",
    "thermal_stability": "sustained_perf_percent",
    "throttle_stability": "sustained_perf_percent",
    "pl1": "sustained_pl1_wattage",
    "pl1_wattage": "sustained_pl1_wattage",
    "wattage": "sustained_pl1_wattage",
    "temp": "thermal_peak_temp_c",
    "surface_temp": "thermal_peak_temp_c",
    "keyboard_temp": "keyboard_deck_temp_c",
    "fan_noise": "fan_noise_dba",
    "noise_dba": "fan_noise_dba",
    "throttle_pct": "thermal_throttle_pct",
    # Camera
    "sensor_size": "sensor_size_inch",
    "ois": "ois_stabilization",
    "dxomark": "dxomark_photo_score",
    "camera_score": "dxomark_photo_score",
    # Battery & Runtime
    "battery_hours": "active_battery_runtime_hours",
    "runtime_hours": "active_battery_runtime_hours",
    "active_runtime": "active_battery_runtime_hours",
    "web_runtime": "web_browsing_runtime_hours",
    "charge_time": "charging_time_minutes",
    "charge_minutes": "charging_time_minutes",
    "charging_time": "charging_time_minutes",
    "battery_mah": "battery_capacity_mah",
    "capacity_mah": "battery_capacity_mah",
    "battery_wh": "battery_capacity_wh",
    "capacity_wh": "battery_capacity_wh",
    # Durability & Build
    "ip": "ip_rating",
    "water_resistance": "ip_rating",
    "ip_water": "ip_water_rating",
    "glass": "glass_protection",
    "frame": "frame_material",
    "ram_upgrade": "ram_upgradeability",
    "ram_slots": "ram_upgradeability",
    "ssd_slot_count": "ssd_slots",
    "hinge": "hinge_chassis_durability",
    # Inverter AC
    "iseer": "iseer_rating",
    "iseer_efficiency": "iseer_rating",
    "derating_52c": "ambient_cooling_derating_52c",
    "coil": "coil_material",
    "condenser_coil": "coil_material",
    "coating": "anti_corrosion_coating",
    "anti_corrosion": "anti_corrosion_coating",
    "idu_noise": "indoor_silent_db",
    "indoor_noise": "indoor_silent_db",
    "compressor_noise": "outdoor_compressor_db",
    "odu_noise": "outdoor_compressor_db",
    "filter": "pm25_filter_ionizer",
    "auto_clean": "auto_clean_ice_wash",
    "pcb_warranty": "pcb_warranty_years",
    "compressor_warranty": "compressor_warranty_years",
    "unit_warranty": "comprehensive_warranty_years",
    # Washing Machine
    "motor": "motor_type",
    "rpm": "max_spin_speed_rpm",
    "spin_rpm": "max_spin_speed_rpm",
    "bee_stars": "bee_star_rating",
    "water_usage": "water_consumption_litres_per_kg",
    "water_l_kg": "water_consumption_litres_per_kg",
    "drum": "drum_material",
    "spider_arm": "spider_arm_corrosion_protection",
    "spin_noise": "spin_noise_db",
    "anti_vibration": "anti_vibration_system",
    "heater": "inbuilt_heater_steam",
    "steam": "inbuilt_heater_steam",
    "smart_features": "smart_connectivity_dosing",
    # Skincare
    "active_pct": "active_concentration_pct",
    "concentration": "active_concentration_pct",
    "clinical_trials": "clinical_trial_evidence",
    "ph_optimality": "ph_target_optimality",
    "ph_score": "ph_target_optimality",
    "stabilizers": "stabilizing_synergists",
    "comedogenic": "comedogenic_rating_max",
    "comedogenic_score": "comedogenic_rating_max",
    "fragrance": "fragrance_free",
    "absorption_seconds": "absorption_speed_seconds",
    "finish_score": "pilling_greasiness_score",
    "packaging": "container_type",
    # Supplements
    "protein_pct": "protein_or_active_purity_pct",
    "purity_pct": "protein_or_active_purity_pct",
    "active_yield": "active_yield_per_serving_g",
    "amino_spiking": "zero_amino_spiking_verified",
    "heavy_metals": "heavy_metals_pass_standard",
    "enzymes": "digestive_enzyme_complex",
    "digestive_enzymes": "digestive_enzyme_complex",
    "bloating_pct": "bloating_complaint_rate_pct",
    "mixability": "mixability_clumping",
    "taste_score": "taste_aftertaste_score",
    "third_party_lab": "third_party_testing_certification",
    "batch_qr": "batch_qr_transparency",
    # TWS Audio
    "harman_deviation": "harman_target_deviation_db",
    "harman_delta": "harman_target_deviation_db",
    "codecs": "hi_res_codec_support",
    "thd": "thd_distortion_pct",
    "anc_db": "anc_noise_attenuation_db",
    "anc_reduction": "anc_noise_attenuation_db",
    "transparency": "transparency_mode_naturalness",
    "mic_snr": "mic_noise_suppression_snr_db",
    "wind_resistance": "wind_noise_resistance",
    "anc_battery_hours": "single_charge_anc_hours",
    "case_hours": "total_case_hours",
    "wireless_charge": "wireless_charging",
    "comfort_score": "ergonomic_comfort_score",
    # IRF Checklist
    "tat_hours": "service_tat_hours",
    "service_tat": "service_tat_hours",
    "tat_days": "service_tat_days",
}


def load_archetypes(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Load default category archetypes from category_archetypes.json."""
    search_paths = []
    if custom_path:
        search_paths.append(custom_path)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths.append(os.path.join(script_dir, "category_archetypes.json"))
    search_paths.append(os.path.join(os.getcwd(), "category_archetypes.json"))
    search_paths.append(
        os.path.expanduser(
            "~/.gemini/config/skills/product-research/scripts/category_archetypes.json"
        )
    )

    for path in search_paths:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                sys.stderr.write(f"[WARN] Failed to read archetypes at {path}: {e}\n")
    return {}


# -----------------------------------------------------------------------------
# Scoring Curve Evaluators
# -----------------------------------------------------------------------------


def evaluate_piecewise_linear(val: float, points: List[List[float]]) -> float:
    """
    Interpolate score along sorted [[x0, y0], [x1, y1], ...] calibration points.
    Clamps between 0.0 and 10.0. Supports both higher-is-better and lower-is-better.
    """
    if not points:
        return 5.0
    sorted_pts = sorted(points, key=lambda p: p[0])

    # Left boundary
    if val <= sorted_pts[0][0]:
        return max(0.0, min(10.0, float(sorted_pts[0][1])))
    # Right boundary
    if val >= sorted_pts[-1][0]:
        return max(0.0, min(10.0, float(sorted_pts[-1][1])))

    # Interval interpolation
    for i in range(len(sorted_pts) - 1):
        x0, y0 = sorted_pts[i][0], sorted_pts[i][1]
        x1, y1 = sorted_pts[i + 1][0], sorted_pts[i + 1][1]
        if x0 <= val <= x1:
            if math.isclose(x0, x1):
                return max(0.0, min(10.0, float(y0)))
            t = (val - x0) / (x1 - x0)
            score = y0 + t * (y1 - y0)
            return max(0.0, min(10.0, float(score)))

    return 5.0


def evaluate_sigmoid(
    val: float, x0: float, k: float, min_score: float = 0.0, max_score: float = 10.0
) -> float:
    """Evaluate sigmoid curve centered at x0 with slope factor k."""
    try:
        score = min_score + (max_score - min_score) / (1.0 + math.exp(-k * (val - x0)))
        return max(0.0, min(10.0, float(score)))
    except OverflowError:
        return 10.0 if k * (val - x0) > 0 else 0.0


def normalize_lookup_key(key: Any) -> str:
    """Normalize categorical lookup strings (lowercase, stripped, underscored)."""
    s = str(key).strip().lower()
    s = re.sub(r"[\s\-\/]+", "_", s)
    s = re.sub(r"[^\w]", "", s)
    return s


def evaluate_discrete(val: Any, options: Dict[str, float]) -> float:
    """
    Evaluate discrete categorical value with case-insensitive and fuzzy alias matching.
    """
    if not options:
        return 5.0

    norm_val = normalize_lookup_key(val)
    norm_options = {normalize_lookup_key(k): float(v) for k, v in options.items()}

    # Exact match
    if norm_val in norm_options:
        return max(0.0, min(10.0, norm_options[norm_val]))

    # Boolean translations
    if isinstance(val, bool) or norm_val in ("true", "yes", "1"):
        for bool_key in ("true", "yes", "1", "verified", "all_verified"):
            if bool_key in norm_options:
                return norm_options[bool_key]
        return 10.0
    if norm_val in ("false", "no", "0"):
        for bool_key in ("false", "no", "0", "none", "unverified"):
            if bool_key in norm_options:
                return norm_options[bool_key]
        return 2.0

    # Substring / fuzzy match
    for opt_k, opt_v in norm_options.items():
        if opt_k in norm_val or norm_val in opt_k:
            return max(0.0, min(10.0, opt_v))

    return 5.0


def evaluate_direct_score(val: Any) -> float:
    """Clamp direct numeric rating (0 to 10 scale)."""
    try:
        f = float(val)
        return max(0.0, min(10.0, f))
    except (ValueError, TypeError):
        return 5.0


def evaluate_curve(curve_type: str, raw_val: Any, metric_def: Dict[str, Any]) -> float:
    """Route measurement value through its specified metric curve."""
    if curve_type == "piecewise_linear":
        try:
            val_num = float(raw_val)
            points = metric_def.get("points", [])
            return evaluate_piecewise_linear(val_num, points)
        except (ValueError, TypeError):
            return 5.0

    if curve_type == "sigmoid":
        try:
            val_num = float(raw_val)
            x0 = float(metric_def.get("x0", 0.0))
            k = float(metric_def.get("k", 1.0))
            return evaluate_sigmoid(val_num, x0, k)
        except (ValueError, TypeError):
            return 5.0

    if curve_type == "discrete":
        options = metric_def.get("options", {})
        return evaluate_discrete(raw_val, options)

    if curve_type == "direct_score":
        return evaluate_direct_score(raw_val)

    return 5.0


# -----------------------------------------------------------------------------
# Defect & Reliability Penalty Engine
# -----------------------------------------------------------------------------


def extract_defect_penalties(
    candidate_defects: List[Union[Dict[str, Any], str]],
    defect_framework: Dict[str, Any],
    dimension_mapping: Dict[str, str],
    category_params: List[str],
) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    """
    Match defects against known failure patterns, calculate penalty deductions
    and maximum parameter score ceilings.
    """
    deductions: Dict[str, float] = {p: 0.0 for p in category_params}
    ceilings: Dict[str, float] = {p: 10.0 for p in category_params}
    audit_log: List[str] = []

    if not candidate_defects:
        return deductions, ceilings, audit_log

    for defect in candidate_defects:
        severity = "moderate"
        affects = None
        issue_text = ""

        if isinstance(defect, dict):
            issue_text = defect.get("issue", defect.get("description", str(defect)))
            severity = defect.get("severity", "moderate").lower()
            affects = defect.get("affects", defect.get("parameter", None))
        else:
            issue_text = str(defect)

        issue_lower = issue_text.lower()

        # If severity not explicitly provided, pattern match against framework
        if isinstance(defect, str) or (isinstance(defect, dict) and "severity" not in defect):
            for sev_key, sev_info in defect_framework.items():
                for pat in sev_info.get("patterns", []):
                    if pat in issue_lower:
                        severity = sev_key
                        break
                if severity == sev_key:
                    break

        sev_config = defect_framework.get(severity, defect_framework.get("moderate", {}))
        penalty = float(sev_config.get("penalty_points", 1.2))
        ceiling = sev_config.get("max_parameter_ceiling")

        # Determine target parameter
        target_param = None
        if affects and affects in category_params:
            target_param = affects
        elif affects and affects in dimension_mapping:
            target_param = dimension_mapping[affects]
        else:
            # Auto-infer affected parameter from text keywords
            if any(k in issue_lower for k in ["motherboard", "dead boot", "solder", "brick"]):
                target_param = "build_durability" if "build_durability" in category_params else category_params[0]
            elif any(k in issue_lower for k in ["green line", "display", "screen", "flicker", "flexgate"]):
                target_param = "display" if "display" in category_params else ("display_accuracy" if "display_accuracy" in category_params else category_params[0])
            elif any(k in issue_lower for k in ["compressor", "refrigerant", "gas leak"]):
                target_param = "cooling_efficiency_iseer" if "cooling_efficiency_iseer" in category_params else category_params[0]
            elif any(k in issue_lower for k in ["spider", "bearing", "drum", "tub"]):
                target_param = "drum_tub_durability" if "drum_tub_durability" in category_params else category_params[0]
            elif any(k in issue_lower for k in ["spiking", "heavy metal", "purity"]):
                target_param = "zero_amino_spiking_heavy_metals" if "zero_amino_spiking_heavy_metals" in category_params else category_params[0]
            elif any(k in issue_lower for k in ["anc", "squeal", "crackling"]):
                target_param = "anc_transparency" if "anc_transparency" in category_params else category_params[0]
            elif any(k in issue_lower for k in ["hinge", "chassis"]):
                target_param = "build_upgradeability" if "build_upgradeability" in category_params else category_params[0]
            else:
                # Fallback to durability or primary category parameter
                target_param = "build_durability" if "build_durability" in category_params else category_params[0]

        deductions[target_param] += penalty
        if ceiling is not None:
            ceilings[target_param] = min(ceilings[target_param], float(ceiling))

        audit_log.append(
            f"Defect '{issue_text}' (Severity: {severity.upper()}) -> -{penalty:.1f} pts on '{target_param}'"
            + (f" (Ceiling: {ceiling})" if ceiling else "")
        )

    return deductions, ceilings, audit_log


# -----------------------------------------------------------------------------
# Deterministic IRF Calculator Engine (0.80 - 1.00)
# -----------------------------------------------------------------------------


def compute_irf(
    candidate: Dict[str, Any], irf_framework: Dict[str, Any]
) -> Tuple[float, Dict[str, Any]]:
    """
    Deterministically calculate Local Environmental & Service Readiness Factor (IRF)
    on a strict scale from 0.80 to 1.00 based on verified checklist data.
    """
    # If readiness_factor or irf explicitly provided as float and no checklist, preserve it
    if "irf_checklist" not in candidate and "readiness" not in candidate:
        if "readiness_factor" in candidate:
            return max(0.80, min(1.00, round(float(candidate["readiness_factor"]), 2))), {
                "method": "explicit",
                "score": float(candidate["readiness_factor"]),
            }
        if "irf" in candidate:
            return max(0.80, min(1.00, round(float(candidate["irf"]), 2))), {
                "method": "explicit",
                "score": float(candidate["irf"]),
            }

    checklist = candidate.get("irf_checklist", candidate.get("readiness", {}))
    weights = irf_framework.get("weights", {
        "service_tat": 0.35,
        "statutory_certification": 0.25,
        "environmental_resilience": 0.25,
        "authorized_seller": 0.15,
    })

    # 1. Service TAT (weight: 0.35)
    tat_score = 0.75  # Default standard national service
    tat_raw = checklist.get("service_tat_hours", checklist.get("tat_hours", checklist.get("service_tat", None)))
    if tat_raw is not None:
        try:
            hrs = float(tat_raw)
            if hrs <= 48:
                tat_score = 1.0
            elif hrs <= 120:
                tat_score = 0.75
            elif hrs <= 240:
                tat_score = 0.40
            else:
                tat_score = 0.10
        except (ValueError, TypeError):
            tat_str = str(tat_raw).lower()
            if any(k in tat_str for k in ["rapid", "under_48", "<48", "fast", "24h"]):
                tat_score = 1.0
            elif any(k in tat_str for k in ["standard", "3-5", "average"]):
                tat_score = 0.75
            elif any(k in tat_str for k in ["extended", "7-10", "regional"]):
                tat_score = 0.40
            elif any(k in tat_str for k in ["poor", "outsourced", ">10", "slow"]):
                tat_score = 0.10
    elif "service_tat_days" in checklist:
        days = float(checklist["service_tat_days"])
        tat_score = 1.0 if days <= 2 else (0.75 if days <= 5 else (0.40 if days <= 10 else 0.10))

    # 2. Statutory Certification (weight: 0.25)
    cert_score = 1.0  # Default verified
    cert_raw = checklist.get("statutory_certifications", checklist.get("statutory_certification", checklist.get("statutory_compliance", None)))
    if cert_raw is not None:
        if isinstance(cert_raw, list):
            cert_score = 1.0 if len(cert_raw) > 0 else 0.0
        elif isinstance(cert_raw, bool):
            cert_score = 1.0 if cert_raw else 0.0
        else:
            cert_str = str(cert_raw).lower()
            if any(k in cert_str for k in ["verified", "all_verified", "compliant", "bis", "bee", "fssai"]):
                cert_score = 1.0
            elif any(k in cert_str for k in ["partial", "pending"]):
                cert_score = 0.5
            elif any(k in cert_str for k in ["grey", "unlicensed", "none", "fail"]):
                cert_score = 0.0

    # 3. Environmental Resilience (weight: 0.25)
    env_score = 0.80  # Default good resilience
    env_raw = checklist.get("environmental_resilience", checklist.get("climate_resilience", None))
    if env_raw is not None:
        if isinstance(env_raw, bool):
            env_score = 1.0 if env_raw else 0.10
        elif isinstance(env_raw, dict):
            # Average sub-features
            sub_vals = [1.0 if v else 0.2 for v in env_raw.values()]
            env_score = sum(sub_vals) / len(sub_vals) if sub_vals else 0.80
        else:
            env_str = str(env_raw).lower()
            if any(k in env_str for k in ["tropical", "resilient", "copper", "ocean_black", "gold_fin", "ip68"]):
                env_score = 1.0
            elif any(k in env_str for k in ["standard", "moderate", "blue_fin"]):
                env_score = 0.60
            elif any(k in env_str for k in ["aluminum", "vulnerable", "none", "unprotected"]):
                env_score = 0.10

    # 4. Authorized Seller Verification (weight: 0.15)
    seller_score = 1.0  # Default official
    seller_raw = checklist.get("authorized_seller", checklist.get("seller_verification", None))
    if seller_raw is not None:
        if isinstance(seller_raw, bool):
            seller_score = 1.0 if seller_raw else 0.0
        else:
            seller_str = str(seller_raw).lower()
            if any(k in seller_str for k in ["brand_authorized", "official", "direct", "true"]):
                seller_score = 1.0
            elif any(k in seller_str for k in ["reputable", "fulfilled", "authorized"]):
                seller_score = 0.75
            elif any(k in seller_str for k in ["unverified", "third_party", "grey", "marketplace"]):
                seller_score = 0.0

    # Weighted composite score in [0.0, 1.0]
    composite_irf = (
        weights["service_tat"] * tat_score
        + weights["statutory_certification"] * cert_score
        + weights["environmental_resilience"] * env_score
        + weights["authorized_seller"] * seller_score
    )

    # Scale to calibrated [0.80, 1.00] range
    irf_final = round(0.80 + 0.20 * composite_irf, 2)
    irf_final = max(0.80, min(1.00, irf_final))

    audit = {
        "service_tat_score": round(tat_score, 2),
        "statutory_cert_score": round(cert_score, 2),
        "environmental_resilience_score": round(env_score, 2),
        "authorized_seller_score": round(seller_score, 2),
        "composite_readiness": round(composite_irf, 4),
        "calibrated_irf": irf_final,
    }
    return irf_final, audit


# -----------------------------------------------------------------------------
# Metric Extraction & Normalization Core
# -----------------------------------------------------------------------------


def extract_and_normalize(
    data: Dict[str, Any],
    archetypes: Dict[str, Any],
    category_override: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Transform raw candidate observations into normalized 0-10 parameter scores
    and calibrated IRF multiplier.
    """
    category = category_override or data.get("category", "smartphones")
    currency = data.get("currency", "INR")
    categories_dict = archetypes.get("categories", archetypes)
    cat_profile = categories_dict.get(category, {})

    if not cat_profile:
        sys.stderr.write(
            f"[WARN] Category '{category}' not found in archetypes. Available: {list(categories_dict.keys())}\n"
        )
        # Attempt fallback to generic or raw input weights
        cat_weights = data.get("weights", {})
        sub_metrics_def = {}
        dim_mapping = {}
    else:
        cat_weights = cat_profile.get("weights", {})
        sub_metrics_def = cat_profile.get("sub_metrics", {})
        dim_mapping = cat_profile.get("dimension_mapping", {})

    defect_framework = archetypes.get("defect_penalties", {})
    irf_framework = archetypes.get("irf_scoring", {})
    category_params = list(cat_weights.keys())

    candidates_raw = data.get("candidates", [])
    if not candidates_raw and isinstance(data, list):
        candidates_raw = data

    normalized_candidates = []

    for cand in candidates_raw:
        name = cand.get("name", "Unknown Contender")
        tier = cand.get("tier", "Standard")
        price = float(cand.get("price", 0.0))

        # Gather measurements (flat and nested)
        raw_measurements = {}
        # 1. Flat candidate measurements dict
        cand_measurements = cand.get("measurements", cand.get("raw_metrics", cand.get("lab_metrics", {})))
        if isinstance(cand_measurements, dict):
            for k, v in cand_measurements.items():
                if isinstance(v, dict):
                    # Nested under parameter name: measurements: {display: {peak_brightness_nits: 1600}}
                    for sub_k, sub_v in v.items():
                        canon = MEASUREMENT_ALIASES.get(sub_k.lower(), sub_k.lower())
                        raw_measurements[canon] = sub_v
                else:
                    canon = MEASUREMENT_ALIASES.get(k.lower(), k.lower())
                    raw_measurements[canon] = v

        # 2. Extract measurements from candidate root keys if present
        for k, v in cand.items():
            if k not in ("name", "tier", "price", "scores", "defects", "irf_checklist", "notes", "measurements"):
                canon = MEASUREMENT_ALIASES.get(k.lower(), k.lower())
                raw_measurements[canon] = v

        candidate_scores_override = cand.get("scores", {})
        candidate_defects = cand.get("defects", cand.get("defect_findings", []))

        # Evaluate sub-metrics per parameter
        param_scores: Dict[str, float] = {}
        extraction_audit: Dict[str, Any] = {}

        for param in category_params:
            param_subs = sub_metrics_def.get(param, {})
            sub_evals = []
            sub_weights = []

            for sub_id, sub_info in param_subs.items():
                canon_id = MEASUREMENT_ALIASES.get(sub_id.lower(), sub_id.lower())
                curve_type = sub_info.get("curve", "piecewise_linear")
                sub_w = float(sub_info.get("weight", 1.0))

                if canon_id in raw_measurements:
                    raw_val = raw_measurements[canon_id]
                    eval_score = evaluate_curve(curve_type, raw_val, sub_info)
                    sub_evals.append((sub_id, eval_score, sub_w, raw_val))
                    sub_weights.append(sub_w)

            if sub_evals:
                # Weighted average of available measured sub-metrics
                total_w = sum(sub_weights)
                param_score = (
                    sum(score * w for _, score, w, _ in sub_evals) / total_w
                    if total_w > 0
                    else 5.0
                )
                extraction_audit[param] = {
                    "derived_from_lab_measurements": True,
                    "sub_metrics": [
                        {
                            "id": sid,
                            "raw": rval,
                            "normalized_score": round(sc, 2),
                            "weight": w,
                        }
                        for sid, sc, w, rval in sub_evals
                    ],
                    "raw_score": round(param_score, 2),
                }
            elif param in candidate_scores_override:
                # Direct score passed in input
                param_score = evaluate_direct_score(candidate_scores_override[param])
                extraction_audit[param] = {
                    "derived_from_lab_measurements": False,
                    "source": "input_scores_override",
                    "raw_score": round(param_score, 2),
                }
            else:
                # Neutral default
                param_score = 7.0
                extraction_audit[param] = {
                    "derived_from_lab_measurements": False,
                    "source": "category_neutral_baseline",
                    "raw_score": 7.0,
                }

            param_scores[param] = param_score

        # Apply defect penalties and ceilings
        deductions, ceilings, defect_logs = extract_defect_penalties(
            candidate_defects, defect_framework, dim_mapping, category_params
        )

        final_param_scores: Dict[str, float] = {}
        for param, score in param_scores.items():
            ded = deductions.get(param, 0.0)
            ceil = ceilings.get(param, 10.0)
            adjusted = max(0.0, score - ded)
            adjusted = min(adjusted, ceil)
            final_param_scores[param] = round(adjusted, 2)
            if ded > 0 or ceil < 10.0:
                extraction_audit[param]["defect_deduction"] = round(ded, 2)
                extraction_audit[param]["ceiling_clamp"] = ceil
                extraction_audit[param]["score_after_penalties"] = round(adjusted, 2)

        # Compute IRF multiplier
        irf_val, irf_audit = compute_irf(cand, irf_framework)

        # Assemble notes
        notes_parts = []
        if cand.get("notes"):
            notes_parts.append(cand["notes"])
        if defect_logs:
            notes_parts.append("Penalties: " + "; ".join(defect_logs))
        notes_parts.append(
            f"IRF: {irf_val:.2f} (TAT Score: {irf_audit.get('service_tat_score', 'N/A')}, Cert: {irf_audit.get('statutory_cert_score', 'N/A')})"
        )
        combined_notes = " | ".join(notes_parts)

        normalized_cand = {
            "name": name,
            "tier": tier,
            "price": price,
            "readiness_factor": irf_val,
            "scores": final_param_scores,
            "notes": combined_notes,
            "extraction_audit": {
                "parameter_breakdown": extraction_audit,
                "irf_audit": irf_audit,
                "defect_penalties": defect_logs,
            },
        }
        normalized_candidates.append(normalized_cand)

        if verbose:
            sys.stderr.write(f"\n--- [AUDIT] {name} ({tier}, Price: {price}) ---\n")
            sys.stderr.write(f"  Calculated IRF: {irf_val:.2f}\n")
            for p, sc in final_param_scores.items():
                orig = param_scores.get(p, sc)
                ded = deductions.get(p, 0.0)
                sys.stderr.write(f"  - {p}: {sc:.2f} (Raw: {orig:.2f}, Deductions: -{ded:.1f})\n")
            if defect_logs:
                sys.stderr.write(f"  Defect Penalties: {', '.join(defect_logs)}\n")

    return {
        "category": category,
        "currency": currency,
        "weights": cat_weights,
        "candidates": normalized_candidates,
    }


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Metric Extractor & Normalization Engine CLI"
    )
    parser.add_argument(
        "-i",
        "--input",
        default="-",
        help="Path to input JSON file or '-' for stdin (default: -)",
    )
    parser.add_argument(
        "-c",
        "--category",
        default=None,
        help="Product category (overrides input JSON category)",
    )
    parser.add_argument(
        "-a",
        "--archetypes",
        default=None,
        help="Path to custom category_archetypes.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to write output normalized JSON (default: stdout)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed audit trace to stderr",
    )

    args = parser.parse_args()

    # Load input observations
    try:
        if args.input == "-" or not args.input:
            raw_input = sys.stdin.read()
            if not raw_input.strip():
                sys.stderr.write("[ERROR] No input JSON provided on stdin.\n")
                sys.exit(1)
            input_data = json.loads(raw_input)
        else:
            with open(args.input, "r", encoding="utf-8") as f:
                input_data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to parse input JSON: {e}\n")
        sys.exit(1)

    # Load archetypes
    archetypes = load_archetypes(args.archetypes)
    if not archetypes:
        sys.stderr.write("[ERROR] Failed to load category archetypes.\n")
        sys.exit(1)

    normalized_data = extract_and_normalize(
        input_data,
        archetypes,
        category_override=args.category,
        verbose=args.verbose,
    )

    output_json = json.dumps(normalized_data, indent=2, ensure_ascii=False)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json + "\n")
            if args.verbose:
                sys.stderr.write(f"[INFO] Normalized JSON written to {args.output}\n")
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to write output file: {e}\n")
            sys.exit(1)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
