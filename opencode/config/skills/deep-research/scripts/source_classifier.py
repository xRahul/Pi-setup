#!/usr/bin/env python3
"""
source_classifier.py — URL normalization, tier classification, dedupe, quota gating.

Functions:
  - normalize_url(url)
  - classify_source(url) -> 1|2|3|4
  - deduplicate_urls(urls)
  - apply_tier_quota(sources) -> (kept, report)
  - build_tier_distribution(sources) -> dict

Usage:
    python source_classifier.py classify <url>
    python source_classifier.py quota <sources.json> [output.json]
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

# Tier 1: primary official / peer-reviewed
TIER1 = re.compile(
    r"(\.gov\b|\.edu\b|\.mil\b|\.int\b"
    r"|who\.int|un\.org|wto\.org|imf\.org|oecd\.org|iso\.org"
    r"|ieee\.org|acm\.org|nist\.gov|uspto\.gov|fda\.gov|ema\.europa\.eu"
    r"|sec\.gov|clinicaltrials\.gov|arxiv\.org|nejm\.org|lancet\.com"
    r"|nature\.com|science\.org|pubmed\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov)",
    re.I,
)
# Tier 2: investigative testing / credentialed journalism
TIER2 = re.compile(
    r"(reuters\.com|bloomberg\.com|wsj\.com|ft\.com|economist\.com"
    r"|nytimes\.com|bbc\.com|ap\.org|nikkei\.com"
    r"|consumerreports\.org|wirecutter\.com|rtings\.com|anandtech\.com"
    r"|tomshardware\.com|ifixit\.com|dpreview\.com|statnews\.com"
    r"|fiercepharma\.com|tradewinds\.com|aviationweek\.com|seriouseats\.com"
    r"|arstechnica\.com)",
    re.I,
)
# Tier 3: community consensus
TIER3 = re.compile(
    r"(reddit\.com|github\.com|stackoverflow\.com|news\.ycombinator\.com"
    r"|g2\.com|capterra\.com|trustpilot\.com|substack\.com|dev\.to)",
    re.I,
)

TRACKING_PARAMS = re.compile(
    r"[?&](utm_[a-z]+|sessionid|fbclid|igshid|ref|gclid|mc_cid|mc_eid)=[^&]*",
    re.I,
)


def normalize_url(url: str) -> str:
    u = url.strip()
    u = re.sub(r"#.*$", "", u)
    u = TRACKING_PARAMS.sub("", u)
    u = re.sub(r"/+$", "", u)
    return u.lower()


def classify_source(url: str) -> int:
    u = url.lower()
    if TIER1.search(u):
        return 1
    if TIER2.search(u):
        return 2
    if TIER3.search(u):
        return 3
    return 4


def deduplicate_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        n = normalize_url(u)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def build_tier_distribution(sources: list[dict[str, Any]]) -> dict[str, int]:
    dist = {"Tier1": 0, "Tier2": 0, "Tier3": 0, "Tier4": 0}
    for s in sources:
        tier = s.get("tier") or classify_source(s.get("url", ""))
        dist[f"Tier{tier}"] += 1
    return dist


def is_bare_root(url: str) -> bool:
    u = url.split("//", 1)[-1] if "//" in url else url
    u = u.split("?", 1)[0].split("#", 1)[0]
    return u.count("/") == 0


def apply_tier_quota(sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter sources and report quota compliance."""
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in sources:
        url = s.get("url", "")
        if not url:
            continue
        norm = normalize_url(url)
        if norm in seen:
            continue
        if is_bare_root(url):
            continue
        seen.add(norm)
        s = dict(s)
        s["url"] = norm
        s.setdefault("tier", classify_source(norm))
        clean.append(s)

    dist = build_tier_distribution(clean)
    total = len(clean) or 1
    t1 = dist["Tier1"]
    t2 = dist["Tier2"]
    t3 = dist["Tier3"]
    t4 = dist["Tier4"]
    high_quality_pct = (t1 + t2) / total * 100
    report = {
        "total_sources": len(clean),
        "tier_distribution": dist,
        "tier1_pct": round(t1 / total * 100, 1),
        "tier2_pct": round(t2 / total * 100, 1),
        "tier3_pct": round(t3 / total * 100, 1),
        "tier4_pct": round(t4 / total * 100, 1),
        "high_quality_pct": round(high_quality_pct, 1),
        "quota_ok": high_quality_pct >= 40.0,
    }
    return clean, report


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: source_classifier.py <classify|quota> ...")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "classify" and len(sys.argv) >= 3:
        print(classify_source(sys.argv[2]))
    elif cmd == "quota" and len(sys.argv) >= 3:
        sources = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        if isinstance(sources, dict) and "sources" in sources:
            sources = sources["sources"]
        kept, report = apply_tier_quota(sources)
        out = {"ok": report["quota_ok"], "kept_sources": kept, "report": report}
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("usage: source_classifier.py <classify|quota> ...")
        sys.exit(2)


if __name__ == "__main__":
    main()
