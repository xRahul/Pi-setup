#!/usr/bin/env python3
"""
Deterministic Product Scorer CLI
Evaluates and ranks product candidates based on normalized multi-parameter weights,
local environmental/service readiness factor (IRF), data confidence tracking,
Value-for-Money (VFM) index, Monte Carlo sensitivity analysis, and flipping thresholds.
"""

import argparse
import json
import os
import random
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


def load_archetypes(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Load default category weights from category_archetypes.json."""
    search_paths = []
    if custom_path:
        search_paths.append(custom_path)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths.append(os.path.join(script_dir, "category_archetypes.json"))
    search_paths.append(os.path.join(os.getcwd(), "category_archetypes.json"))
    search_paths.append(
        os.path.expanduser("~/.gemini/config/skills/product-research/scripts/category_archetypes.json")
    )

    for path in search_paths:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("categories", data)
            except Exception as e:
                sys.stderr.write(f"[WARN] Failed to read archetypes at {path}: {e}\n")
    return {}


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Normalize weights to ensure sum(w_i) == 1.0."""
    total = sum(weights.values())
    if total <= 0:
        count = len(weights)
        if count == 0:
            return {}
        return {k: 1.0 / count for k in weights}
    return {k: v / total for k, v in weights.items()}


def format_currency(price: float, currency: str) -> str:
    """Format price with currency symbol or code."""
    c = currency.upper().strip()
    if c in ("INR", "RS", "RUPEE", "RUPEES", "₹"):
        return f"₹{price:,.0f}" if price.is_integer() else f"₹{price:,.2f}"
    if c in ("USD", "$"):
        return f"${price:,.0f}" if price.is_integer() else f"${price:,.2f}"
    if c in ("EUR", "€"):
        return f"€{price:,.0f}" if price.is_integer() else f"€{price:,.2f}"
    if c in ("GBP", "£"):
        return f"£{price:,.0f}" if price.is_integer() else f"£{price:,.2f}"
    return f"{c} {price:,.2f}"


def compute_candidate_confidence(
    cand: Dict[str, Any],
    norm_weights: Dict[str, float],
    archetypes: Dict[str, Any],
    category: str,
) -> Tuple[float, str, str, float]:
    """
    Computes data confidence score (0.0 to 100.0), tier, badge flag, and imputed penalty.
    Tiers:
      - HIGH (Verified Lab/Teardown): >= 80%
      - MEDIUM (Corroborated Specs): 50% to 79%
      - LOW (Imputed/Sparse): < 50%
    """
    conf_val: Optional[float] = None

    # 1. Explicit candidate confidence
    if "confidence" in cand:
        raw_conf = cand["confidence"]
        if isinstance(raw_conf, (int, float)):
            val = float(raw_conf)
            conf_val = val * 100.0 if 0.0 <= val <= 1.0 else min(100.0, max(0.0, val))
        elif isinstance(raw_conf, str):
            c_upper = raw_conf.strip().upper()
            if "HIGH" in c_upper:
                conf_val = 90.0
            elif "MED" in c_upper:
                conf_val = 65.0
            elif "LOW" in c_upper:
                conf_val = 35.0
            else:
                match = re.search(r"(\d+(\.\d+)?)", raw_conf)
                if match:
                    val = float(match.group(1))
                    conf_val = val * 100.0 if val <= 1.0 else min(100.0, max(0.0, val))

    # 2. Extraction audit parameter breakdown (from metric_extractor.py)
    if conf_val is None:
        audit = cand.get("extraction_audit", {})
        breakdown = audit.get("parameter_breakdown", {})
        if breakdown:
            total_w = sum(norm_weights.get(p, 1.0) for p in norm_weights) or 1.0
            verified_w = 0.0
            for p, w in norm_weights.items():
                info = breakdown.get(p, {})
                if info.get("derived_from_lab_measurements", False):
                    verified_w += w * 1.0
                elif info.get("source") == "input_scores_override":
                    verified_w += w * 0.70
                elif info.get("source") == "category_neutral_baseline":
                    verified_w += w * 0.0
                else:
                    verified_w += w * 0.50
            conf_val = (verified_w / total_w) * 100.0

    # 3. Verified parameters list
    if conf_val is None and "verified_parameters" in cand:
        v_params = cand["verified_parameters"]
        if isinstance(v_params, list):
            total_w = sum(norm_weights.get(p, 1.0) for p in norm_weights) or 1.0
            verified_w = sum(norm_weights.get(p, 1.0) for p in v_params if p in norm_weights)
            conf_val = (verified_w / total_w) * 100.0

    # 4. Evidence count
    if conf_val is None and "evidence_count" in cand:
        try:
            ev_count = float(cand["evidence_count"])
            target_count = float(len(norm_weights)) if norm_weights else 5.0
            conf_val = min(100.0, max(0.0, (ev_count / max(1.0, target_count)) * 100.0))
        except (ValueError, TypeError):
            pass

    # 5. Measurements dictionary count
    if conf_val is None and "measurements" in cand:
        meas = cand["measurements"]
        if isinstance(meas, dict):
            target_count = float(len(norm_weights)) if norm_weights else 6.0
            meas_count = float(len(meas))
            conf_val = min(100.0, max(0.0, (meas_count / max(1.0, target_count)) * 100.0))

    # 6. Fallback based on score completeness against archetype parameters
    if conf_val is None:
        cat_info = archetypes.get(category, {})
        archetype_params = set()
        if isinstance(cat_info, dict) and "weights" in cat_info:
            archetype_params = set(cat_info["weights"].keys())
        elif isinstance(cat_info, dict):
            archetype_params = set(cat_info.keys())
        if not archetype_params and norm_weights:
            archetype_params = set(norm_weights.keys())

        cand_scores = cand.get("scores", {})
        if archetype_params:
            provided_count = len([p for p in archetype_params if p in cand_scores])
            completeness = provided_count / len(archetype_params)
            if completeness >= 1.0:
                conf_val = 90.0 if (cand.get("notes") or cand.get("irf_checklist")) else 80.0
            elif completeness >= 0.70:
                conf_val = completeness * 80.0
            else:
                conf_val = completeness * 70.0
        else:
            conf_val = 80.0 if cand_scores else 50.0

    conf_score = round(min(100.0, max(0.0, conf_val)), 1)

    # Assign Tier and Penalty
    if conf_score >= 80.0:
        tier = "HIGH (Verified Lab/Teardown)"
        flag = "HIGH"
        penalty = 0.0
    elif conf_score >= 50.0:
        tier = "MEDIUM (Corroborated Specs)"
        flag = "MED"
        penalty = round((80.0 - conf_score) / 100.0 * 0.25, 3)
    else:
        tier = "LOW (Imputed/Sparse)"
        flag = "⚠️ LOW"
        penalty = round(0.10 + (50.0 - conf_score) / 100.0 * 0.50, 3)

    return conf_score, tier, flag, penalty


def compute_flipping_thresholds(
    ranked_candidates: List[Dict[str, Any]],
    norm_weights: Dict[str, float],
    currency: str,
) -> Dict[str, Any]:
    """Calculate exact parameter delta, weight delta, and price discount for #2 to overtake #1."""
    if len(ranked_candidates) < 2:
        return {"message": "Single candidate evaluated; no nearest challenger to flip."}

    leader = ranked_candidates[0]
    challenger = ranked_candidates[1]
    gap = round(leader["final_score"] - challenger["final_score"], 2)

    M_C = challenger["readiness_factor"] * (1.0 - challenger.get("confidence_penalty", 0.0))
    M_L = leader["readiness_factor"] * (1.0 - leader.get("confidence_penalty", 0.0))

    # Parameter Deltas for Challenger to overtake Leader on Final Score
    param_deltas: Dict[str, Dict[str, Any]] = {}
    for param, weight in norm_weights.items():
        if weight <= 0 or M_C <= 0:
            continue
        delta_s = gap / (weight * M_C) if gap > 0 else 0.0
        curr_s = challenger["parameter_scores"].get(param, 0.0)
        target_s = curr_s + delta_s
        achievable = target_s <= 10.001
        param_deltas[param] = {
            "current_score": round(curr_s, 2),
            "delta_required": round(delta_s, 2),
            "target_score": round(min(10.0, target_s), 2),
            "achievable": achievable,
        }

    # Weight Deltas for Challenger to overtake Leader on Final Score
    weight_deltas: Dict[str, Dict[str, Any]] = {}
    v_C = {k: challenger["parameter_scores"].get(k, 0.0) * M_C for k in norm_weights}
    v_L = {k: leader["parameter_scores"].get(k, 0.0) * M_L for k in norm_weights}

    for param, weight in norm_weights.items():
        if weight >= 0.999:
            continue
        v_L_other = sum(norm_weights[j] * v_L[j] for j in norm_weights if j != param) / (1.0 - weight)
        v_C_other = sum(norm_weights[j] * v_C[j] for j in norm_weights if j != param) / (1.0 - weight)
        D = (v_C[param] - v_L[param]) - (v_C_other - v_L_other)
        if D > 0.001 and gap > 0:
            delta_w = gap / D
            target_w = weight + delta_w
            achievable = target_w <= 1.0001
            weight_deltas[param] = {
                "current_weight": round(weight, 4),
                "weight_delta_required": round(delta_w, 4),
                "target_weight": round(min(1.0, target_w), 4),
                "achievable": achievable,
            }

    # Price / VFM Flipping Threshold
    P_L = leader["price"]
    P_C = challenger["price"]
    S_L = leader["final_score"]
    S_C = challenger["final_score"]
    vfm_L = leader["vfm_index"]
    vfm_C = challenger["vfm_index"]

    vfm_threshold: Dict[str, Any] = {}
    if vfm_C > vfm_L:
        # Challenger already leads in VFM
        discount_needed_L = 0.0
        target_P_L = P_L
        if S_C > 0 and P_L > 0:
            target_P_L = P_C * (S_L / S_C)
            discount_needed_L = max(0.0, P_L - target_P_L)
        disc_pct_L = (discount_needed_L / P_L * 100.0) if P_L > 0 else 0.0
        vfm_threshold = {
            "status": "challenger_already_leads",
            "leader_vfm": round(vfm_L, 2),
            "challenger_vfm": round(vfm_C, 2),
            "discount_required_for_leader": round(discount_needed_L, 2),
            "discount_pct": round(disc_pct_L, 1),
            "discount_formatted": format_currency(discount_needed_L, currency),
            "target_price": round(target_P_L, 2),
            "target_price_formatted": format_currency(target_P_L, currency),
        }
    else:
        # Leader leads in VFM; Challenger must drop price
        discount_needed_C = 0.0
        target_P_C = P_C
        if S_L > 0 and P_C > 0:
            target_P_C = P_L * (S_C / S_L)
            discount_needed_C = max(0.0, P_C - target_P_C)
        disc_pct_C = (discount_needed_C / P_C * 100.0) if P_C > 0 else 0.0
        vfm_threshold = {
            "status": "leader_leads",
            "leader_vfm": round(vfm_L, 2),
            "challenger_vfm": round(vfm_C, 2),
            "discount_required_for_challenger": round(discount_needed_C, 2),
            "discount_pct": round(disc_pct_C, 1),
            "discount_formatted": format_currency(discount_needed_C, currency),
            "target_price": round(target_P_C, 2),
            "target_price_formatted": format_currency(target_P_C, currency),
        }

    return {
        "leader": leader["name"],
        "challenger": challenger["name"],
        "score_gap": gap,
        "parameter_deltas": param_deltas,
        "weight_deltas": weight_deltas,
        "price_vfm_threshold": vfm_threshold,
    }


def compute_price_elasticity(candidates: List[Dict[str, Any]], currency: str) -> Dict[str, List[Dict[str, Any]]]:
    """Calculate VFM impact across 5%, 10%, and 15% instant discounts."""
    results: Dict[str, List[Dict[str, Any]]] = {}
    for cand in candidates:
        price = cand["price"]
        final_score = cand["final_score"]
        base_vfm = cand["vfm_index"]
        c_discounts = []
        for pct in (5, 10, 15):
            discount_mult = 1.0 - (pct / 100.0)
            disc_price = price * discount_mult
            disc_vfm = (final_score / (disc_price / 1000.0) * 100.0) if disc_price > 0 else 0.0
            vfm_gain_pct = ((disc_vfm - base_vfm) / base_vfm * 100.0) if base_vfm > 0 else 0.0
            c_discounts.append({
                "discount_pct": pct,
                "discounted_price": round(disc_price, 2),
                "discounted_price_formatted": format_currency(disc_price, currency),
                "vfm_index": round(disc_vfm, 2),
                "vfm_gain_pct": round(vfm_gain_pct, 1),
            })
        results[cand["name"]] = c_discounts
    return results


def score_candidates(
    data: Dict[str, Any],
    archetypes: Dict[str, Any],
    mc_iterations: int = 100,
    seed: int = 42,
) -> Dict[str, Any]:
    """Process candidates, compute weighted scores, IRF, confidence, sensitivity, and VFM."""
    category = data.get("category", "generic")
    currency = data.get("currency", "INR")
    raw_weights = data.get("weights")

    if not raw_weights:
        cat_info = archetypes.get(category, {})
        if isinstance(cat_info, dict) and "weights" in cat_info:
            raw_weights = cat_info["weights"]
        elif isinstance(cat_info, dict):
            raw_weights = cat_info
        else:
            raw_weights = {}

    candidates_raw = data.get("candidates", [])
    if not candidates_raw:
        return {
            "category": category,
            "currency": currency,
            "weights": {},
            "ranked_candidates": [],
            "champions": {},
            "sensitivity_analysis": {},
        }

    # If weights not predefined, infer from union of candidate score keys
    if not raw_weights:
        all_keys = set()
        for c in candidates_raw:
            all_keys.update(c.get("scores", {}).keys())
        raw_weights = {k: 1.0 for k in all_keys}

    # Ensure only numeric weights are passed to normalize_weights
    if isinstance(raw_weights, dict):
        raw_weights = {k: float(v) for k, v in raw_weights.items() if isinstance(v, (int, float))}

    norm_weights = normalize_weights(raw_weights)

    evaluated = []
    for cand in candidates_raw:
        name = cand.get("name", "Unknown Product")
        tier = cand.get("tier", "Standard")
        price = float(cand.get("price", 0.0))
        readiness = float(cand.get("readiness_factor", cand.get("irf", 1.0)))
        readiness = max(0.0, min(1.0, readiness))

        scores = cand.get("scores", {})
        overall_score = 0.0
        scored_breakdown = {}
        for param, weight in norm_weights.items():
            param_score = float(scores.get(param, 0.0))
            param_score = max(0.0, min(10.0, param_score))
            overall_score += param_score * weight
            scored_breakdown[param] = round(param_score, 2)

        # Compute Confidence Score, Tier, Badge Flag, and Imputed Penalty
        conf_score, conf_tier, conf_flag, conf_penalty = compute_candidate_confidence(
            cand, norm_weights, archetypes, category
        )

        unadjusted_final_score = overall_score * readiness
        # Apply confidence discount to prevent unverified candidates from outranking lab-tested candidates
        final_score = unadjusted_final_score * (1.0 - conf_penalty)

        # VFM Index = (Final Score / (Price / 1000)) * 100
        if price > 0:
            vfm_index = (final_score / (price / 1000.0)) * 100.0
        else:
            vfm_index = 0.0

        evaluated.append({
            "name": name,
            "tier": tier,
            "price": price,
            "price_formatted": format_currency(price, currency),
            "readiness_factor": round(readiness, 2),
            "confidence_score": conf_score,
            "confidence_tier": conf_tier,
            "confidence_flag": conf_flag,
            "confidence_penalty": conf_penalty,
            "overall_score": round(overall_score, 2),
            "unadjusted_final_score": round(unadjusted_final_score, 2),
            "final_score": round(final_score, 2),
            "vfm_index": round(vfm_index, 2),
            "parameter_scores": scored_breakdown,
            "notes": cand.get("notes", ""),
        })

    # Sort primarily by final_score descending, then vfm_index descending, then confidence_score descending
    ranked = sorted(
        evaluated,
        key=lambda x: (x["final_score"], x["vfm_index"], x["confidence_score"]),
        reverse=True,
    )
    for idx, item in enumerate(ranked, 1):
        item["rank"] = idx

    base_ranks = {item["name"]: item["rank"] for item in ranked}

    # Automated Sensitivity & Perturbation Engine (Monte Carlo weight perturbation ±10% to ±20%)
    retention_counts = {item["name"]: 0 for item in ranked}
    if len(ranked) > 1 and norm_weights:
        rng = random.Random(seed)
        for _ in range(mc_iterations):
            # Perturb each weight by ±10% to ±20%
            perturbed_w = {}
            for k, w in norm_weights.items():
                delta = rng.uniform(-0.20, 0.20)
                perturbed_w[k] = max(0.001, w * (1.0 + delta))
            tot_w = sum(perturbed_w.values())
            p_norm = {k: v / tot_w for k, v in perturbed_w.items()}

            iter_eval = []
            for item in evaluated:
                p_ovr = sum(item["parameter_scores"].get(k, 0.0) * p_norm[k] for k in p_norm)
                p_unadj = p_ovr * item["readiness_factor"]
                p_fin = round(p_unadj * (1.0 - item["confidence_penalty"]), 2)
                p_vfm = round((p_fin / (item["price"] / 1000.0)) * 100.0, 2) if item["price"] > 0 else 0.0
                iter_eval.append((item["name"], p_fin, p_vfm, item["confidence_score"]))

            iter_eval.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
            for r_idx, (cname, _, _, _) in enumerate(iter_eval, 1):
                if r_idx == base_ranks[cname]:
                    retention_counts[cname] += 1
    else:
        for item in ranked:
            retention_counts[item["name"]] = mc_iterations

    # Record rank stability on candidates
    for item in ranked:
        cname = item["name"]
        stab_pct = round((retention_counts[cname] / max(1, mc_iterations)) * 100.0, 1)
        item["rank_stability_pct"] = stab_pct
        if stab_pct >= 90.0:
            item["stability_tier"] = "Solid"
        elif stab_pct >= 70.0:
            item["stability_tier"] = "Stable"
        else:
            item["stability_tier"] = "Fragile"

    # Determine Champions
    overall_winner = ranked[0] if ranked else None
    vfm_champion = max(ranked, key=lambda x: x["vfm_index"]) if ranked else None

    # Tier Champions
    tiers = {}
    for item in ranked:
        t = item["tier"]
        if t not in tiers:
            tiers[t] = item

    # Winner Robustness
    winner_robustness = {}
    if overall_winner:
        w_stab = overall_winner["rank_stability_pct"]
        if w_stab >= 90.0:
            w_rob_tier = "ROBUST (Solid Winner)"
        elif w_stab >= 70.0:
            w_rob_tier = "MODERATE (Stable Pick)"
        else:
            w_rob_tier = "FRAGILE (Coin-Flip Pick)"
        winner_robustness = {
            "winner_name": overall_winner["name"],
            "stability_pct": w_stab,
            "robustness_tier": w_rob_tier,
        }

    # Flipping Thresholds and Price Elasticity
    flipping_thresholds = compute_flipping_thresholds(ranked, norm_weights, currency)
    price_elasticity = compute_price_elasticity(ranked, currency)

    for item in ranked:
        item["price_sensitivity"] = price_elasticity.get(item["name"], [])

    sensitivity_analysis = {
        "monte_carlo_iterations": mc_iterations,
        "weight_perturbation_range": "±10% to ±20%",
        "winner_robustness": winner_robustness,
        "candidate_stability": [
            {
                "name": item["name"],
                "rank": item["rank"],
                "stability_pct": item["rank_stability_pct"],
                "tier": item["stability_tier"],
            }
            for item in ranked
        ],
        "flipping_thresholds": flipping_thresholds,
        "price_elasticity": price_elasticity,
    }

    return {
        "category": category,
        "currency": currency,
        "normalized_weights": {k: round(v, 4) for k, v in norm_weights.items()},
        "ranked_candidates": ranked,
        "champions": {
            "overall_winner": overall_winner,
            "vfm_champion": vfm_champion,
            "tier_champions": tiers,
        },
        "sensitivity_analysis": sensitivity_analysis,
    }


def render_markdown(results: Dict[str, Any]) -> str:
    """Render GitHub-flavored markdown output."""
    ranked = results.get("ranked_candidates", [])
    if not ranked:
        return "_No candidates evaluated._\n"

    weights = results.get("normalized_weights", {})
    category = results.get("category", "General")
    champions = results.get("champions", {})
    currency = results.get("currency", "INR")
    sensitivity = results.get("sensitivity_analysis", {})

    lines = []
    lines.append(f"### Deterministic Multi-Parameter Comparison Matrix ({category.replace('_', ' ').title()})")
    lines.append("")

    # Summary table header with Confidence and Stability columns
    header = ["Rank", "Product", "Tier", "Price", "Final Score", "IRF", "Confidence", "Stability", "VFM Index"]
    separator = ["---", "---", "---", "---", "---", "---", "---", "---", "---"]

    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(separator) + " |")

    has_low_conf = False
    for item in ranked:
        conf_tier = item.get("confidence_tier", "MEDIUM")
        conf_score = item.get("confidence_score", 70.0)
        if "LOW" in conf_tier:
            has_low_conf = True
            conf_str = f"⚠️ LOW ({conf_score:.0f}%)"
        elif "HIGH" in conf_tier:
            conf_str = f"HIGH ({conf_score:.0f}%)"
        else:
            conf_str = f"MED ({conf_score:.0f}%)"

        stab_pct = item.get("rank_stability_pct", 100.0)
        stab_tier = item.get("stability_tier", "Solid")
        stab_str = f"{stab_pct:.0f}% ({stab_tier})"

        row = [
            f"**#{item['rank']}**",
            f"**{item['name']}**",
            item["tier"],
            item["price_formatted"],
            f"**{item['final_score']:.2f}**/10",
            f"{item['readiness_factor']:.2f}",
            conf_str,
            stab_str,
            f"{item['vfm_index']:.2f}",
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    if has_low_conf:
        lines.append("> [!WARNING]")
        lines.append("> **Data Confidence Alert**: Candidates flagged with `⚠️ LOW` have missing or unverified metrics (<50% completeness). An imputed uncertainty discount has been applied to prevent unverified products from outranking lab-tested contenders.")
        lines.append("")

    # Detailed Parameter Score Breakdown Table
    params = list(weights.keys())
    if params:
        lines.append("#### Parameter Breakdown (Normalized Weights)")
        p_headers = ["Product"] + [f"{p.replace('_', ' ').title()} ({w*100:.0f}%)" for p, w in weights.items()]
        p_sep = ["---"] * len(p_headers)
        lines.append("| " + " | ".join(p_headers) + " |")
        lines.append("| " + " | ".join(p_sep) + " |")

        for item in ranked:
            p_row = [item["name"]]
            for p in params:
                val = item["parameter_scores"].get(p, 0.0)
                p_row.append(f"{val:.1f}")
            lines.append("| " + " | ".join(p_row) + " |")
        lines.append("")

    # Champions Callouts
    lines.append("#### Evaluation Champions")
    overall = champions.get("overall_winner")
    vfm = champions.get("vfm_champion")
    tier_champs = champions.get("tier_champions", {})

    if overall:
        conf_info = f", Confidence: {overall.get('confidence_score', 0):.0f}%" if "confidence_score" in overall else ""
        stab_info = f", Stability: {overall.get('rank_stability_pct', 0):.0f}%" if "rank_stability_pct" in overall else ""
        lines.append(f"- 🏆 **Overall Winner**: **{overall['name']}** — Final Score: **{overall['final_score']:.2f}/10** ({overall['price_formatted']}{conf_info}{stab_info})")
    if vfm:
        lines.append(f"- 💡 **Value-for-Money (VFM) Champion**: **{vfm['name']}** — VFM Index: **{vfm['vfm_index']:.2f}** ({vfm['price_formatted']}, Score: {vfm['final_score']:.2f})")

    if tier_champs:
        tier_str = ", ".join([f"**{t}**: {c['name']} ({c['final_score']:.2f})" for t, c in tier_champs.items()])
        lines.append(f"- 🥇 **Tier Champions**: {tier_str}")

    lines.append("")

    # Sensitivity & Rank Stability Audit Section
    if sensitivity:
        lines.append("#### Sensitivity & Rank Stability Audit")
        lines.append("")
        w_rob = sensitivity.get("winner_robustness", {})
        if w_rob:
            w_name = w_rob.get("winner_name", "Leader")
            w_stab = w_rob.get("stability_pct", 100.0)
            w_tier = w_rob.get("robustness_tier", "ROBUST")
            mc_runs = sensitivity.get("monte_carlo_iterations", 100)
            lines.append(f"- **Winner Robustness**: **{w_tier}** ({w_stab:.1f}% Rank Stability across {mc_runs} weight permutations)")
            lines.append(f"  - **#{ranked[0]['rank']} {w_name}** preserved #1 ranking in **{w_stab:.1f}%** of randomized weight tests (±10% to ±20% perturbation).")
            c_stabs = sensitivity.get("candidate_stability", [])
            if len(c_stabs) > 1:
                lines.append("  - **Candidate Stability Breakdown**:")
                for cs in c_stabs:
                    lines.append(f"    - **{cs['name']}** (#{cs['rank']}): **{cs['stability_pct']:.1f}%** retention ({cs['tier']})")

        # Flipping Thresholds
        flips = sensitivity.get("flipping_thresholds", {})
        if flips and "challenger" in flips:
            leader_name = flips.get("leader", "Leader")
            chall_name = flips.get("challenger", "Challenger")
            gap = flips.get("score_gap", 0.0)
            lines.append("")
            lines.append(f"- **Nearest Challenger Flipping Thresholds** (**{chall_name}** vs **{leader_name}**):")
            lines.append(f"  - **Score Gap**: **{gap:.2f} pts**")

            # Parameter deltas
            p_deltas = flips.get("parameter_deltas", {})
            if p_deltas:
                achievable_deltas = [
                    f"**{p.replace('_', ' ').title()}**: +{d['delta_required']:.2f} pts (target {d['target_score']:.2f}/10)"
                    for p, d in p_deltas.items() if d.get("achievable")
                ]
                if achievable_deltas:
                    lines.append(f"  - **Viable Parameter Improvements for {chall_name} to Overtake #1**:")
                    for ad in achievable_deltas:
                        lines.append(f"    - {ad}")
                else:
                    lines.append(f"  - **Parameter Score Deltas**: Score gap ({gap:.2f} pts) cannot be overcome by a single parameter improvement alone (all exceed 10.0 scale ceiling).")

            # Weight deltas
            w_deltas = flips.get("weight_deltas", {})
            if w_deltas:
                achievable_weights = [
                    f"**{p.replace('_', ' ').title()} Weight**: +{d['weight_delta_required']:.4f} (from {d['current_weight']*100:.1f}% to {d['target_weight']*100:.1f}%)"
                    for p, d in w_deltas.items() if d.get("achievable")
                ]
                if achievable_weights:
                    lines.append(f"  - **Priority Weight Sensitivity (Weight Shifts for {chall_name} to Overtake #1)**:")
                    for aw in achievable_weights:
                        lines.append(f"    - {aw}")

            # Price / VFM flip
            vfm_flip = flips.get("price_vfm_threshold", {})
            if vfm_flip:
                status = vfm_flip.get("status")
                if status == "challenger_already_leads":
                    lines.append(f"  - **Value-for-Money Status**: **{chall_name}** already leads in VFM Index ({vfm_flip.get('challenger_vfm'):.2f} vs {vfm_flip.get('leader_vfm'):.2f}).")
                    if vfm_flip.get("discount_required_for_leader", 0) > 0:
                        lines.append(f"    - For **{leader_name}** to overtake in VFM, its price must drop by **{vfm_flip['discount_formatted']}** ({vfm_flip['discount_pct']:.1f}% discount).")
                elif status == "leader_leads":
                    lines.append(f"  - **Value-for-Money Flipping Discount**: For **{chall_name}** to overtake **{leader_name}** in VFM Index, its price must drop by **{vfm_flip['discount_formatted']}** ({vfm_flip['discount_pct']:.1f}% discount to {vfm_flip['target_price_formatted']}).")

        # Price Elasticity
        p_sens = sensitivity.get("price_elasticity", {})
        if p_sens:
            lines.append("")
            lines.append("- **Price Elasticity & Discount Sensitivity (Instant Card / Sale Discounts)**:")
            for c_name, disc_list in p_sens.items():
                disc_strs = [
                    f"{d['discount_pct']}%: {d['discounted_price_formatted']} (VFM **{d['vfm_index']:.2f}**, +{d['vfm_gain_pct']:.1f}%)"
                    for d in disc_list
                ]
                lines.append(f"  - **{c_name}**: " + " | ".join(disc_strs))

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Deterministic Product Scorer CLI")
    parser.add_argument(
        "-i", "--input", default="-", help="Path to input JSON file or '-' for stdin (default: -)"
    )
    parser.add_argument(
        "-a", "--archetypes", default=None, help="Path to custom category_archetypes.json"
    )
    parser.add_argument(
        "--mc-iterations", type=int, default=100, help="Number of Monte Carlo iterations for sensitivity testing (default: 100)"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducible Monte Carlo sensitivity testing (default: 42)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw structured evaluation JSON"
    )
    parser.add_argument(
        "--markdown", action="store_true", help="Output formatted GitHub-flavored markdown (default)"
    )

    args = parser.parse_args()

    # Load input data
    try:
        if args.input == "-" or not args.input:
            raw_input = sys.stdin.read()
            if not raw_input.strip():
                sys.stderr.write("[ERROR] No input provided on stdin.\n")
                sys.exit(1)
            data = json.loads(raw_input)
        else:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to parse input JSON: {e}\n")
        sys.exit(1)

    archetypes = load_archetypes(args.archetypes)
    results = score_candidates(data, archetypes, mc_iterations=args.mc_iterations, seed=args.seed)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(results))


if __name__ == "__main__":
    main()
