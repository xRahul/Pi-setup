#!/usr/bin/env python3
"""
Source evaluation, URL normalization, authority tier classification,
and citation verification for deep-research.
"""

import html
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Tracking query parameters to strip
TRACKING_PARAMS: Set[str] = {
    "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "twclid", "dclid",
    "ref", "ref_src", "ref_url", "source", "feature", "trk", "tracking",
    "mc_cid", "mc_eid", "yclid", "_hsenc", "_hsmi", "igshid", "si", "spm",
    "ncid", "guccounter", "guce_referrer", "guce_referrer_sig",
}

# Subdomain prefixes for primary company documentation, investor relations, and developer portals
PRIMARY_DOCS_SUBDOMAINS: Tuple[str, ...] = (
    "docs.", "support.", "developer.", "developers.", "investor.", "investors."
)

# TLD Suffixes for Tier 1 (Government, Education, Military, Intergovernmental)
TIER_1_TLD_SUFFIXES: Tuple[str, ...] = (
    ".gov", ".mil", ".edu", ".int",
    ".gov.uk", ".gov.au", ".gov.in", ".gov.sg", ".gov.ca", ".gov.za", ".gov.br", ".gov.cn",
    ".gouv.fr", ".gob.es", ".gob.mx", ".gob.ar",
    ".go.jp", ".go.kr", ".go.id",
    ".edu.au", ".edu.cn", ".edu.in", ".edu.sg", ".edu.tw", ".edu.br", ".edu.mx",
    ".ac.uk", ".ac.in", ".ac.jp", ".ac.nz", ".ac.za", ".ac.kr", ".ac.il",
)

# Tier 1: Primary Official & Authoritative
# - Standards bodies (ISO, ASTM, ANSI, IEEE, ACM, NIST, USPTO, FDA, EMA, SEC)
# - Intergovernmental treaty organizations (WHO, UN, WTO, IMF, World Bank, OECD, etc.)
# - Medical & biomedical primary registries (PubMed, NCBI, Cochrane Library, ClinicalTrials.gov, NEJM, Lancet, BMJ, Nature, Science, Cell, JAMA, Mayo Clinic)
# - Geopolitical & defense institutions (CSIS, RAND, IISS, SIPRI, Brookings, CFR, Chatham House, UNCTAD)
# - Primary academic publishers & universities
TIER_1_EXACT_DOMAINS: Set[str] = {
    # Academic & Scientific Publishers / Preprints
    "arxiv.org", "nature.com", "science.org", "sciencemag.org", "cell.com", "pnas.org",
    "biorxiv.org", "medrxiv.org", "plos.org", "plosone.org", "nber.org",
    "springer.com", "wiley.com", "sciencedirect.com", "oup.com", "cambridge.org",
    "jstor.org", "cern.ch", "nasa.gov",
    # Top Universities / Academic Centers
    "mit.edu", "stanford.edu", "harvard.edu", "berkeley.edu", "ox.ac.uk", "cam.ac.uk",
    # Intergovernmental & Treaty Organizations
    "who.int", "un.org", "wto.org", "imf.org", "worldbank.org", "oecd.org",
    "unctad.org", "iaea.org", "bis.org", "europa.eu", "ec.europa.eu", "ema.europa.eu",
    "consilium.europa.eu", "europarl.europa.eu", "unclos.org",
    # Standards Bodies & Regulators
    "iso.org", "astm.org", "ansi.org", "ieee.org", "acm.org", "nist.gov",
    "uspto.gov", "fda.gov", "sec.gov", "w3.org", "ietf.org", "rfc-editor.org",
    "itu.int", "cen.eu", "cenelec.eu", "etsi.org", "din.de", "bsigroup.com",
    # Medical Registries & Biomedical Institutions
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "nih.gov", "pubmed.gov",
    "cochranelibrary.com", "cochrane.org", "clinicaltrials.gov",
    "nejm.org", "thelancet.com", "thelancet.org", "bmj.com", "jamanetwork.com",
    "mayoclinic.org", "mayo.edu", "cdc.gov",
    # Geopolitical & Defense Think Tanks
    "csis.org", "rand.org", "iiss.org", "sipri.org", "brookings.edu", "brookings.org",
    "cfr.org", "chathamhouse.org", "carnegieendowment.org", "rusi.org", "atlanticcouncil.org",
}

# Tier 2: Investigative Journalism, Benchmarks & Independent Testing Labs
# - Established Global Journalism (Reuters, Bloomberg, WSJ, FT, Economist, NYT, WaPo, BBC, AP, Guardian, Nikkei Asia)
# - Independent Testing Labs & Consumer Benchmarks (Consumer Reports, Wirecutter, RTings, AnandTech, Tom's Hardware, iFixit, GSMArena, DPReview)
# - Specialized Industry Journalism (StatNews, FiercePharma, Defense One, Aviation Week, Lloyd's List, TradeWinds, Serious Eats, Eater, The Verge, Wired, Ars Technica)
TIER_2_EXACT_DOMAINS: Set[str] = {
    # Global Investigative Journalism
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "economist.com",
    "nytimes.com", "washingtonpost.com", "bbc.com", "bbc.co.uk", "apnews.com",
    "theguardian.com", "guardian.co.uk", "nikkei.com", "asia.nikkei.com",
    "forbes.com", "fortune.com", "cnbc.com",
    # Independent Testing Labs & Consumer Benchmarks
    "consumerreports.org", "wirecutter.com", "thewirecutter.com", "rtings.com",
    "anandtech.com", "tomshardware.com", "ifixit.com", "gsmarena.com",
    "dpreview.com", "notebookcheck.net", "dxomark.com", "geekerwan.com",
    # Specialized Industry Journalism: Pharma & Healthcare
    "statnews.com", "fiercepharma.com", "fiercebiotech.com", "fiercehealthcare.com",
    "endpoints.news", "biopharmadive.com",
    # Specialized Industry Journalism: Defense & Aerospace
    "defenseone.com", "aviationweek.com", "flightglobal.com", "janes.com",
    "defensenews.com", "breakingdefense.com",
    # Specialized Industry Journalism: Maritime & Logistics
    "lloydslist.com", "lloydslist.maritimeintelligence.informa.com",
    "tradewindsnews.com", "splash247.com", "maritime-executive.com",
    # Specialized Industry Journalism: Food Science & Culinary
    "seriouseats.com", "eater.com", "guide.michelin.com", "michelin.com",
    "americastestkitchen.com",
    # Specialized Technology & Industry Journalism
    "theverge.com", "wired.com", "arstechnica.com", "venturebeat.com", "zdnet.com",
    "techcrunch.com", "semianalysis.com", "theinformation.com", "infoworld.com",
    "mittechnologyreview.com", "protocol.com", "spectrum.ieee.org", "huggingface.co",
    # Code Repositories (Baseline)
    "github.com",
}

# Tier 3: Practitioner & Community Consensus
# - High-Signal Community Forums (Reddit discussions, Stack Exchange, Hacker News)
# - Software & Consumer Review Platforms (G2, Capterra, Trustpilot)
# - Practitioner & Curated Expert Publishing (Substack, Medium)
TIER_3_DOMAINS: Set[str] = {
    # High-Signal Discussion Forums & Q&A
    "reddit.com", "redd.it", "old.reddit.com",
    "stackexchange.com", "stackoverflow.com", "serverfault.com", "superuser.com",
    "askubuntu.com", "mathoverflow.net",
    "news.ycombinator.com", "quora.com", "discourse.org",
    # Software & Product Review Aggregators
    "g2.com", "capterra.com", "trustpilot.com", "yelp.com", "tripadvisor.com",
    # Practitioner Newsletters & Publishing
    "substack.com", "medium.com", "dev.to", "hashnode.com",
    # Social Discussion Networks
    "linkedin.com", "twitter.com", "x.com", "threads.net", "facebook.com",
    "instagram.com", "youtube.com",
}


def clean_url(url: str) -> str:
    """
    Strips tracking queries (utm_*, fbclid, gclid, ref, etc.) and
    normalizes canonical endpoints.
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    # Unescape any HTML entities in URL
    url = html.unescape(url)

    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    if scheme not in ("http", "https"):
        return ""

    netloc = parsed.netloc.lower()
    # Remove default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path: collapse multi-slashes
    path = re.sub(r"/+", "/", parsed.path)
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    # Parse and clean query parameters
    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    cleaned_query: List[Tuple[str, str]] = []
    for k, v in query_items:
        k_lower = k.lower()
        if k_lower.startswith("utm_"):
            continue
        if k_lower in TRACKING_PARAMS:
            continue
        cleaned_query.append((k, v))

    cleaned_query.sort(key=lambda x: x[0])
    query_str = urllib.parse.urlencode(cleaned_query)

    # Clean fragment: omit empty fragments or common tracking fragments
    fragment = parsed.fragment
    if fragment.startswith(("_=_", "heading-", ":~:text=")):
        fragment = ""

    return urllib.parse.urlunsplit((scheme, netloc, path, query_str, fragment))


def is_valid_source_url(url: str) -> bool:
    """
    Rejects bare root domains (e.g. https://example.com/ without a path/slug).
    Requires a valid HTTP/HTTPS URL with an informative path or query.
    """
    if not url or not isinstance(url, str):
        return False

    cleaned = clean_url(url)
    if not cleaned:
        return False

    parsed = urllib.parse.urlsplit(cleaned)
    if not parsed.netloc or "." not in parsed.netloc:
        return False

    # Check for bare root domain (path is empty or "/" and no query)
    path_clean = parsed.path.strip("/")
    if not path_clean and not parsed.query:
        return False

    # Ignore search engines or common index roots
    if parsed.netloc in ("google.com", "www.google.com", "bing.com", "www.bing.com", "duckduckgo.com"):
        if not parsed.query:
            return False

    return True


def resolve_canonical_url(url: str, timeout: float = 2.5) -> str:
    """
    Resolves Google Search grounding redirects or HTTP redirects.
    Safely falls back to cleaned input URL if network/timeout fails.
    """
    if not url:
        return ""

    cleaned = clean_url(url)
    if not cleaned:
        return ""

    parsed = urllib.parse.urlsplit(cleaned)

    # Fast-path: Google search redirect (e.g. google.com/url?q=... or /url?url=...)
    if "google." in parsed.netloc and parsed.path.endswith("/url"):
        query_dict = dict(urllib.parse.parse_qsl(parsed.query))
        target = query_dict.get("q") or query_dict.get("url")
        if target:
            return clean_url(target)

    # Fast-path for common grounding/proxy redirects
    if "vertexaisearch.cloud.google.com" in parsed.netloc or "grounding" in parsed.netloc:
        query_dict = dict(urllib.parse.parse_qsl(parsed.query))
        target = query_dict.get("url") or query_dict.get("q")
        if target:
            return clean_url(target)

    # Attempt HTTP HEAD / GET to follow 301/302 redirects
    try:
        req = urllib.request.Request(
            cleaned,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0; +https://opencode.ai)"},
            method="HEAD"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            return clean_url(final_url)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and "Location" in e.headers:
            redirect_target = urllib.parse.urljoin(cleaned, e.headers["Location"])
            return clean_url(redirect_target)
        # On 403/405 (HEAD blocked), return cleaned
        return cleaned
    except (urllib.error.URLError, TimeoutError, OSError, Exception):
        # Fallback to cleaned URL on connection failure or timeout
        return cleaned


def classify_domain_tier(domain_or_url: str) -> int:
    """
    Domain Authority Classifier (Tiers 1 to 4):
    - Tier 1 (Primary Official & Authoritative):
        Gov, Edu, Intergovernmental (.int, WHO, UN, WTO, IMF, World Bank, OECD),
        standards bodies (ISO, ASTM, ANSI, IEEE, ACM, NIST, USPTO, FDA, EMA, SEC),
        medical registries (PubMed, Cochrane, ClinicalTrials.gov, NEJM, Lancet, BMJ, Nature, Science, Cell, JAMA, Mayo Clinic),
        geopolitical think tanks (CSIS, RAND, IISS, SIPRI, Brookings, CFR, Chatham House, UNCTAD),
        primary company documentation, developer portals, investor relations (docs.*, support.*, developer.*, investor.*).
    - Tier 2 (Investigative Journalism, Benchmarks & Independent Testing Labs):
        Established global journalism (Reuters, Bloomberg, WSJ, FT, Economist, NYT, WaPo, BBC, AP, Guardian, Nikkei Asia),
        independent testing labs & consumer benchmarks (Consumer Reports, Wirecutter, RTings, AnandTech, Tom's Hardware, iFixit, GSMArena, DPReview),
        specialized industry journalism (StatNews, FiercePharma, Defense One, Aviation Week, Lloyd's List, TradeWinds, Serious Eats, Eater, The Verge, Wired, Ars Technica).
    - Tier 3 (Practitioner & Community Consensus):
        High-signal community forums (Reddit discussions, Stack Exchange, GitHub issues/discussions, Hacker News, G2, Capterra, Trustpilot, curated expert Substacks).
    - Tier 4 / Default (General Web / Unclassified Blogs):
        General unverified websites, generic affiliate blogs, promotional pages.
    """
    if not domain_or_url or not isinstance(domain_or_url, str):
        return 4

    domain_or_url = domain_or_url.strip()
    if not domain_or_url:
        return 4

    if "://" in domain_or_url:
        parsed = urllib.parse.urlsplit(domain_or_url)
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
    else:
        if "/" in domain_or_url:
            parts = domain_or_url.split("/", 1)
            netloc = parts[0].lower()
            path = "/" + parts[1].lower()
        else:
            netloc = domain_or_url.lower()
            path = ""

    if ":" in netloc:
        netloc = netloc.split(":")[0]

    # Strip leading www. or m.
    if netloc.startswith("www."):
        domain = netloc[4:]
    elif netloc.startswith("m."):
        domain = netloc[2:]
    else:
        domain = netloc

    # Special handling for Wirecutter under nytimes.com
    if domain == "nytimes.com" and (path.startswith("/wirecutter") or "wirecutter" in path):
        return 2

    # Community consensus path checks (GitHub issues, discussions, PRs)
    if domain in ("github.com", "gitlab.com") and (
        "/issues" in path or "/discussions" in path or "/pull" in path
    ):
        return 3

    # Primary company documentation, investor relations, and developer portals
    if domain.startswith(PRIMARY_DOCS_SUBDOMAINS):
        return 1

    # Check Tier 1 Suffixes (.gov, .edu, .ac.uk, .int, .mil, etc.)
    for suffix in TIER_1_TLD_SUFFIXES:
        if domain.endswith(suffix):
            return 1

    # Check Tier 1 Exact / Parent Domains
    if domain in TIER_1_EXACT_DOMAINS:
        return 1
    for d in TIER_1_EXACT_DOMAINS:
        if domain.endswith("." + d):
            return 1

    # Check Tier 2 Exact / Parent Domains
    if domain in TIER_2_EXACT_DOMAINS:
        return 2
    for d in TIER_2_EXACT_DOMAINS:
        if domain.endswith("." + d):
            return 2

    # Check Tier 3 Exact / Parent Domains
    if domain in TIER_3_DOMAINS:
        return 3
    for d in TIER_3_DOMAINS:
        if domain.endswith("." + d):
            return 3

    # Generic discussion forum / review path or subdomain indicators
    if any(p in path for p in ("/forum/", "/forums/", "/discussion/", "/discussions/", "/comments/", "/thread/", "/threads/", "/reviews/")):
        return 3
    if any(domain.startswith(sub) for sub in ("forum.", "forums.", "community.", "boards.", "discuss.")):
        return 3

    # Tier 4 / Default (General Web / Unclassified Blogs)
    return 4


def classify_source_category(url: str, title: str = "") -> str:
    """
    Returns categorical tag:
    - "primary_official": Government, academic, standards bodies, biomedical registries,
      geopolitical think tanks, primary company documentation & specs.
    - "investigative_testing": Established investigative journalism, independent testing labs,
      consumer benchmarks, specialized industry reporting.
    - "community_consensus": High-signal community forums, Reddit discussions, Stack Exchange,
      GitHub issues/discussions, software/product reviews (G2/Capterra/Trustpilot).
    - "general_web": Unclassified websites, generic blogs, marketing pages.
    """
    if not url or not isinstance(url, str):
        return "general_web"

    tier = classify_domain_tier(url)

    # Contextual override if unclassified but title strongly indicates community discussion
    if tier == 4 and title:
        title_lower = title.lower()
        if any(term in title_lower for term in ("reddit", "forum", "discussion thread", "user review", "capterra", "g2 review")):
            return "community_consensus"

    tier_category_map = {
        1: "primary_official",
        2: "investigative_testing",
        3: "community_consensus",
        4: "general_web",
    }
    return tier_category_map.get(tier, "general_web")


def build_citation_map(
    raw_sources: List[Union[str, Dict[str, Any]]],
    resolve_redirects: bool = True
) -> Dict[str, Any]:
    """
    Deduplicates URLs, assigns sequential citation numbers [1], [2], ...,
    classifies source authority tier (1 to 4) and category tag,
    and computes credibility and category distribution.
    """
    seen_urls: Set[str] = set()
    citations: Dict[int, Dict[str, Any]] = {}
    url_to_index: Dict[str, int] = {}
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    category_counts = {
        "primary_official": 0,
        "investigative_testing": 0,
        "community_consensus": 0,
        "general_web": 0,
    }

    current_index = 1

    for item in raw_sources:
        if isinstance(item, str):
            raw_url = item
            title = ""
            snippet = ""
        elif isinstance(item, dict):
            raw_url = item.get("url", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
        else:
            continue

        if not is_valid_source_url(raw_url):
            continue

        canonical_url = resolve_canonical_url(raw_url) if resolve_redirects else clean_url(raw_url)
        if not canonical_url or not is_valid_source_url(canonical_url):
            continue

        if canonical_url in seen_urls:
            # If already seen, optionally update title if current one was empty
            existing_idx = url_to_index[canonical_url]
            if not citations[existing_idx]["title"] and title:
                citations[existing_idx]["title"] = title
            continue

        seen_urls.add(canonical_url)
        url_to_index[canonical_url] = current_index

        parsed = urllib.parse.urlsplit(canonical_url)
        domain = parsed.netloc

        tier = classify_domain_tier(canonical_url)
        source_category = classify_source_category(canonical_url, title)

        # Synchronize tier if category was promoted by title
        if source_category == "community_consensus" and tier == 4:
            tier = 3

        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        category_counts[source_category] = category_counts.get(source_category, 0) + 1

        if not title:
            # Fallback title from domain and path slug
            path_slug = parsed.path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ").title()
            title = f"{domain}: {path_slug}" if path_slug else domain

        citations[current_index] = {
            "index": current_index,
            "url": canonical_url,
            "title": title,
            "domain": domain,
            "tier": tier,
            "source_category": source_category,
            "snippet": snippet,
        }
        current_index += 1

    total = len(citations)
    distribution = {
        "tier_1_count": tier_counts[1],
        "tier_2_count": tier_counts[2],
        "tier_3_count": tier_counts[3],
        "tier_4_count": tier_counts[4],
        "tier_1_pct": round((tier_counts[1] / total * 100), 1) if total > 0 else 0.0,
        "tier_2_pct": round((tier_counts[2] / total * 100), 1) if total > 0 else 0.0,
        "tier_3_pct": round((tier_counts[3] / total * 100), 1) if total > 0 else 0.0,
        "tier_4_pct": round((tier_counts[4] / total * 100), 1) if total > 0 else 0.0,
        "source_category_distribution": category_counts,
        "community_consensus_count": category_counts["community_consensus"],
        "total": total,
    }

    return {
        "citations": citations,
        "url_to_index": url_to_index,
        "credibility_distribution": distribution,
    }


def verify_citations(report_text: str, citation_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Programmatically confirms that all body citation anchors [N] exist in the
    reference bibliography and citation map, and detects unresolved placeholder anchors.
    """
    citations = citation_map.get("citations", {})
    # Normalize keys to ints
    valid_indexes: Set[int] = {int(k) for k in citations.keys() if str(k).isdigit() or isinstance(k, int)}

    # Match citation anchors [1], [2], [12] that are NOT part of a markdown link [1](http...)
    pattern = r"\[(\d+)\](?!\()"
    matches = re.findall(pattern, report_text)
    cited_in_body: Set[int] = {int(m) for m in matches}

    missing_indexes = sorted(list(cited_in_body - valid_indexes))
    unused_indexes = sorted(list(valid_indexes - cited_in_body))

    errors: List[str] = []
    if missing_indexes:
        for idx in missing_indexes:
            errors.append(f"Citation anchor [{idx}] used in report text but missing from citation bibliography.")

    # Detect ungrounded citation placeholders like [N], [TODO], [TBD]
    placeholders = re.findall(r"\[(N|TODO|TBD|\?)\](?!\()", report_text)
    if placeholders:
        for p in sorted(list(set(placeholders))):
            errors.append(f"Unresolved citation placeholder '[{p}]' found in report text.")

    is_valid = len(missing_indexes) == 0 and len(placeholders) == 0

    return {
        "valid": is_valid,
        "total_citations_defined": len(valid_indexes),
        "total_inline_occurrences": len(matches),
        "cited_indexes": sorted(list(cited_in_body)),
        "missing_indexes": missing_indexes,
        "unused_indexes": unused_indexes,
        "errors": errors,
    }


def format_bibliography_entry(citation: Dict[str, Any]) -> str:
    """
    Formats a single bibliography entry in standard publication format:
    [N] **Title** — [URL](URL) (Tier X: Source Category: Domain)
    """
    idx = citation.get("index", 1)
    title = (citation.get("title") or "").strip() or citation.get("domain", "Source")
    url = (citation.get("url") or "").strip()
    tier = citation.get("tier", 4)
    cat = citation.get("source_category", "general_web")
    domain = citation.get("domain", "")
    if not domain and url:
        parsed = urllib.parse.urlsplit(url)
        domain = parsed.netloc

    return f"[{idx}] **{title}** — [{url}]({url}) (Tier {tier}: {cat}: {domain})"


def format_bibliography(
    citation_map_or_citations: Union[Dict[str, Any], Dict[int, Dict[str, Any]]],
    cited_indexes: Optional[Set[int]] = None
) -> str:
    """
    Formats a complete markdown bibliography list from a citation map or citations dict.
    If cited_indexes is provided, only formats entries for those indices (in sorted order).
    """
    if not citation_map_or_citations:
        return ""

    if isinstance(citation_map_or_citations, dict) and "citations" in citation_map_or_citations:
        citations_dict = citation_map_or_citations["citations"]
    elif isinstance(citation_map_or_citations, dict):
        citations_dict = citation_map_or_citations
    else:
        return ""

    entries: List[str] = []
    # Sort keys as ints
    sorted_keys = sorted([int(k) for k in citations_dict.keys() if str(k).isdigit() or isinstance(k, int)])

    for idx in sorted_keys:
        if cited_indexes is not None and idx not in cited_indexes:
            continue
        c = citations_dict[idx]
        if isinstance(c, dict):
            entry_dict = dict(c)
            if "index" not in entry_dict:
                entry_dict["index"] = idx
            entries.append(format_bibliography_entry(entry_dict))

    return "\n".join(entries)


def ensure_report_bibliography(
    report_text: str,
    citation_map: Dict[str, Any],
    cited_only: bool = False
) -> str:
    """
    Ensures Section 7 Reference Bibliography is present, correctly formatted,
    and populated with all cited (or indexed) sources without placeholders.
    """
    citations = citation_map.get("citations", {})
    if not citations:
        return report_text

    cited_indexes = None
    if cited_only:
        pattern = r"\[(\d+)\](?!\()"
        matches = re.findall(pattern, report_text)
        cited_indexes = {int(m) for m in matches if int(m) in citations}

    bib_md = format_bibliography(citations, cited_indexes=cited_indexes)

    # Check for Section 7 header in text
    section_pattern = r"(## 7\.\s*Reference Bibliography[^\n]*\n)(.*)$"
    match = re.search(section_pattern, report_text, re.DOTALL | re.IGNORECASE)

    if match:
        header = match.group(1)
        prefix = report_text[:match.start()]
        return f"{prefix}{header}\n{bib_md}\n"
    else:
        # Check for non-numbered header
        alt_pattern = r"(##\s*Reference Bibliography[^\n]*\n)(.*)$"
        alt_match = re.search(alt_pattern, report_text, re.DOTALL | re.IGNORECASE)
        if alt_match:
            prefix = report_text[:alt_match.start()]
            return f"{prefix}## 7. Reference Bibliography\n\n{bib_md}\n"
        else:
            return f"{report_text.rstrip()}\n\n## 7. Reference Bibliography\n\n{bib_md}\n"

