#!/usr/bin/env python3
"""
Unit tests for the deep-research skill.
Tests source evaluation, domain classification, citation verification,
HTML parsing, and workflow compilation.
"""

import ast
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import eval_sources
import gap_analysis
import read_page


class TestSourceEvaluation(unittest.TestCase):

    def test_clean_url_strips_tracking(self):
        """Test that clean_url strips UTM parameters, fbclid, gclid, and other trackers."""
        dirty_url = (
            "https://example.com/research/paper-1?utm_source=twitter&utm_medium=social"
            "&fbclid=IwAR2xyz&gclid=12345&id=42&ref=banner"
        )
        cleaned = eval_sources.clean_url(dirty_url)
        self.assertEqual(cleaned, "https://example.com/research/paper-1?id=42")

    def test_clean_url_normalization(self):
        """Test scheme, port, and trailing slash normalization."""
        url_with_port = "http://example.com:80/docs/index.html/"
        cleaned = eval_sources.clean_url(url_with_port)
        self.assertEqual(cleaned, "http://example.com/docs/index.html")

        # Upper case domain
        url_upper = "HTTPS://WWW.EXAMPLE.COM/path"
        cleaned_upper = eval_sources.clean_url(url_upper)
        self.assertEqual(cleaned_upper, "https://www.example.com/path")

    def test_is_valid_source_url_rejects_bare_root(self):
        """Test that bare root domains without paths or slugs are rejected."""
        self.assertFalse(eval_sources.is_valid_source_url("https://example.com"))
        self.assertFalse(eval_sources.is_valid_source_url("https://example.com/"))
        self.assertFalse(eval_sources.is_valid_source_url("http://google.com/"))
        self.assertFalse(eval_sources.is_valid_source_url(""))
        self.assertFalse(eval_sources.is_valid_source_url("not-a-url"))

        # Valid URLs with paths or slugs
        self.assertTrue(eval_sources.is_valid_source_url("https://arxiv.org/abs/2401.00001"))
        self.assertTrue(eval_sources.is_valid_source_url("https://example.com/article/deep-research"))
        self.assertTrue(eval_sources.is_valid_source_url("https://docs.python.org/3/library/ast.html"))

    def test_resolve_canonical_url_google_redirect(self):
        """Test extraction of target URL from Google search grounding redirects."""
        redirect_url = (
            "https://www.google.com/url?q=https%3A%2F%2Farxiv.org%2Fabs%2F2401.00001"
            "&sa=U&ved=2ahUKEwj"
        )
        resolved = eval_sources.resolve_canonical_url(redirect_url)
        self.assertEqual(resolved, "https://arxiv.org/abs/2401.00001")

    def test_domain_tier_classification(self):
        """Test Domain Authority Tier classification logic across all 4 tiers."""
        # Tier 1: Primary Official & Authoritative
        # Academic & Preprints
        self.assertEqual(eval_sources.classify_domain_tier("https://arxiv.org/abs/2401.00001"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.nature.com/articles/s41586-024"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://ai.stanford.edu/research"), 1)
        # Government, Regulators & Standards
        self.assertEqual(eval_sources.classify_domain_tier("https://www.sec.gov/edgar/searchedgar"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.nist.gov/publications"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.fda.gov/drugs/development-approval-process"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.ema.europa.eu/en/medicines"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.iso.org/standard/72140.html"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.astm.org/standards/e100"), 1)
        # Medical & Biomedical Primary Registries
        self.assertEqual(eval_sources.classify_domain_tier("https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD013214.pub2/full"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://pubmed.ncbi.nlm.nih.gov/38123456/"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://clinicaltrials.gov/study/NCT05123456"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.nejm.org/doi/full/10.1056/NEJMoa2300001"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.mayoclinic.org/diseases-conditions/diabetes"), 1)
        # Intergovernmental & Treaty Bodies
        self.assertEqual(eval_sources.classify_domain_tier("https://www.who.int/news/item/01-01-2024"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.worldbank.org/en/publication/global-economic-prospects"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://unclos.org/convention"), 1)
        # Geopolitical Think Tanks
        self.assertEqual(eval_sources.classify_domain_tier("https://www.csis.org/analysis/future-semiconductor-supply-chains"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.rand.org/pubs/research_reports/RRA123-1.html"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.iiss.org/online-analysis/military-balance/2024/02/"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.sipri.org/databases/armstransfers"), 1)
        # Primary Company Documentation, Developer Portals, Investor Relations
        self.assertEqual(eval_sources.classify_domain_tier("https://docs.python.org/3/library/ast.html"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://developer.mozilla.org/en-US/docs/Web"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://support.apple.com/en-us/HT201222"), 1)
        self.assertEqual(eval_sources.classify_domain_tier("https://investor.apple.com/financials/default.aspx"), 1)

        # Tier 2: Investigative Journalism, Benchmarks & Independent Testing Labs
        # Global Investigative Journalism
        self.assertEqual(eval_sources.classify_domain_tier("https://www.reuters.com/technology/ai-update"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.bloomberg.com/news/articles"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.wsj.com/tech/personal-tech/reviews"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.ft.com/content/00000000"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://techcrunch.com/2024/01/01/deep-tech"), 2)
        # Independent Testing Labs & Consumer Benchmarks
        self.assertEqual(eval_sources.classify_domain_tier("https://www.consumerreports.org/cars/hybrids-evs/best-hybrid-cars-a1234/"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.rtings.com/tv/reviews/best/by-size/65-inch"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.nytimes.com/wirecutter/reviews/best-soundbar/"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://wirecutter.com/reviews/best-running-shoes/"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.ifixit.com/Teardown/iPhone+15+Pro+Teardown/12345"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.gsmarena.com/samsung_galaxy_s24_ultra-review-2665.php"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.anandtech.com/show/18718/cpu-benchmarks"), 2)
        # Specialized Industry Journalism (Pharma, Defense, Maritime, Food Science, Tech)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.statnews.com/2024/01/01/biotech-pipeline"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.fiercepharma.com/pharma/drug-approvals-tracker"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.defenseone.com/threats/2024/01/drones/"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://aviationweek.com/aerospace/commercial-aviation"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.lloydslist.com/LL12345/tanker-freight-rates"), 2)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.seriouseats.com/the-food-lab-reverse-sear-steak"), 2)
        # Code Repositories (Baseline)
        self.assertEqual(eval_sources.classify_domain_tier("https://github.com/google/antigravity"), 2)

        # Tier 3: Practitioner & Community Consensus
        # Discussion Forums & Q&A
        self.assertEqual(eval_sources.classify_domain_tier("https://www.reddit.com/r/technology/comments/12345/discussion/"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://stackoverflow.com/questions/123456/how-to-fix-bug"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://stats.stackexchange.com/questions/999/p-value-interpretation"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://news.ycombinator.com/item?id=39000000"), 3)
        # GitHub Issues & Discussions
        self.assertEqual(eval_sources.classify_domain_tier("https://github.com/astral-sh/uv/issues/999"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://github.com/facebook/react/discussions/101"), 3)
        # Review Platforms
        self.assertEqual(eval_sources.classify_domain_tier("https://www.g2.com/products/slack/reviews"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.capterra.com/p/12345/reviews/"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://www.trustpilot.com/review/example.com"), 3)
        # Practitioner Newsletters & Publishing
        self.assertEqual(eval_sources.classify_domain_tier("https://medium.com/@user/my-thoughts"), 3)
        self.assertEqual(eval_sources.classify_domain_tier("https://news.substack.com/p/future-trends"), 3)

        # Tier 4: General Web / Unclassified Blogs
        self.assertEqual(eval_sources.classify_domain_tier("https://randomblog.xyz/post/123"), 4)
        self.assertEqual(eval_sources.classify_domain_tier("https://affiliate-top-deals.net/best-vpn-2026/"), 4)

    def test_classify_source_category(self):
        """Test Source Category classification logic."""
        # Primary Official
        self.assertEqual(
            eval_sources.classify_source_category("https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD013214.pub2/full"),
            "primary_official"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://pubmed.ncbi.nlm.nih.gov/38123456/"),
            "primary_official"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://clinicaltrials.gov/study/NCT05123456"),
            "primary_official"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://www.csis.org/analysis/future-semiconductor-supply-chains"),
            "primary_official"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://docs.python.org/3/library/ast.html"),
            "primary_official"
        )

        # Investigative Testing
        self.assertEqual(
            eval_sources.classify_source_category("https://www.consumerreports.org/cars/hybrids-evs/best-hybrid-cars-a1234/"),
            "investigative_testing"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://www.rtings.com/tv/reviews/best/by-size/65-inch"),
            "investigative_testing"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://www.nytimes.com/wirecutter/reviews/best-soundbar/"),
            "investigative_testing"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://www.statnews.com/2024/01/01/biotech-pipeline"),
            "investigative_testing"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://www.seriouseats.com/the-food-lab-reverse-sear-steak"),
            "investigative_testing"
        )

        # Community Consensus
        self.assertEqual(
            eval_sources.classify_source_category("https://www.reddit.com/r/technology/comments/12345/discussion/"),
            "community_consensus"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://github.com/astral-sh/uv/issues/999"),
            "community_consensus"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://stackoverflow.com/questions/123456/how-to-fix-bug"),
            "community_consensus"
        )
        self.assertEqual(
            eval_sources.classify_source_category("https://www.g2.com/products/slack/reviews"),
            "community_consensus"
        )

        # General Web
        self.assertEqual(
            eval_sources.classify_source_category("https://randomblog.xyz/post/123"),
            "general_web"
        )

    def test_build_citation_map(self):
        """Test deduplication, authority tiering, and citation indexing."""
        sources = [
            {"url": "https://arxiv.org/abs/2401.00001?utm_source=hackernews", "title": "Paper 1"},
            {"url": "https://arxiv.org/abs/2401.00001", "title": "Duplicate Paper 1"},
            {"url": "https://techcrunch.com/2024/01/15/report", "title": "TechCrunch Article"},
            {"url": "https://substack.com/p/deep-dive", "title": "Blog Post"},
            {"url": "https://example.com/", "title": "Bare root domain - should be dropped"},
        ]

        citation_map = eval_sources.build_citation_map(sources, resolve_redirects=False)
        citations = citation_map["citations"]
        dist = citation_map["credibility_distribution"]

        # 3 valid unique sources
        self.assertEqual(len(citations), 3)
        self.assertEqual(citations[1]["url"], "https://arxiv.org/abs/2401.00001")
        self.assertEqual(citations[1]["tier"], 1)
        self.assertEqual(citations[1]["source_category"], "primary_official")

        self.assertEqual(citations[2]["url"], "https://techcrunch.com/2024/01/15/report")
        self.assertEqual(citations[2]["tier"], 2)
        self.assertEqual(citations[2]["source_category"], "investigative_testing")

        self.assertEqual(citations[3]["url"], "https://substack.com/p/deep-dive")
        self.assertEqual(citations[3]["tier"], 3)
        self.assertEqual(citations[3]["source_category"], "community_consensus")

        self.assertEqual(dist["tier_1_count"], 1)
        self.assertEqual(dist["tier_2_count"], 1)
        self.assertEqual(dist["tier_3_count"], 1)
        self.assertEqual(dist["tier_4_count"], 0)
        self.assertEqual(dist["community_consensus_count"], 1)
        self.assertEqual(dist["source_category_distribution"]["primary_official"], 1)
        self.assertEqual(dist["source_category_distribution"]["investigative_testing"], 1)
        self.assertEqual(dist["source_category_distribution"]["community_consensus"], 1)
        self.assertEqual(dist["source_category_distribution"]["general_web"], 0)
        self.assertEqual(dist["total"], 3)

    def test_build_citation_map_broad_domains_and_community_consensus(self):
        """
        Test build_citation_map with consumer testing labs, medical registries,
        geopolitical think tanks, and community consensus forums.
        """
        diverse_sources = [
            # Tier 1 / Primary Official
            {"url": "https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD013214.pub2/full", "title": "Cochrane Systematic Review"},
            {"url": "https://clinicaltrials.gov/study/NCT05123456", "title": "Clinical Trial Registry"},
            {"url": "https://www.csis.org/analysis/future-semiconductor-supply-chains", "title": "CSIS Supply Chain Analysis"},
            # Tier 2 / Investigative Testing
            {"url": "https://www.rtings.com/tv/reviews/best/by-size/65-inch", "title": "RTings TV Lab Measurements"},
            {"url": "https://www.consumerreports.org/cars/hybrids-evs/best-hybrid-cars-a1234/", "title": "Consumer Reports Vehicle Testing"},
            {"url": "https://www.statnews.com/2024/01/01/biotech-pipeline", "title": "StatNews Biotech Investigative Report"},
            # Tier 3 / Community Consensus
            {"url": "https://www.reddit.com/r/technology/comments/12345/discussion/", "title": "Reddit Real-World User Experiences"},
            {"url": "https://github.com/astral-sh/uv/issues/999", "title": "GitHub Issue Bug Report"},
            # Tier 4 / General Web
            {"url": "https://randomblog.xyz/post/123", "title": "Unverified Affiliate Post"},
        ]

        citation_map = eval_sources.build_citation_map(diverse_sources, resolve_redirects=False)
        citations = citation_map["citations"]
        dist = citation_map["credibility_distribution"]

        self.assertEqual(len(citations), 9)
        self.assertEqual(dist["total"], 9)

        # Tier breakdown
        self.assertEqual(dist["tier_1_count"], 3)
        self.assertEqual(dist["tier_2_count"], 3)
        self.assertEqual(dist["tier_3_count"], 2)
        self.assertEqual(dist["tier_4_count"], 1)

        # Source category breakdown
        self.assertEqual(dist["community_consensus_count"], 2)
        cat_dist = dist["source_category_distribution"]
        self.assertEqual(cat_dist["primary_official"], 3)
        self.assertEqual(cat_dist["investigative_testing"], 3)
        self.assertEqual(cat_dist["community_consensus"], 2)
        self.assertEqual(cat_dist["general_web"], 1)

        # Verify individual citations
        self.assertEqual(citations[1]["source_category"], "primary_official")
        self.assertEqual(citations[1]["tier"], 1)

        self.assertEqual(citations[4]["source_category"], "investigative_testing")
        self.assertEqual(citations[4]["tier"], 2)

        self.assertEqual(citations[7]["source_category"], "community_consensus")
        self.assertEqual(citations[7]["tier"], 3)

        self.assertEqual(citations[9]["source_category"], "general_web")
        self.assertEqual(citations[9]["tier"], 4)

    def test_verify_citations(self):
        """Test citation verification in report markdown."""
        citation_map = {
            "citations": {
                1: {"url": "https://arxiv.org/abs/1"},
                2: {"url": "https://reuters.com/tech"},
                3: {"url": "https://nature.com/articles/1"},
            }
        }

        # Valid text citing [1] and [2]
        valid_report = "According to initial benchmarks [1], latency dropped by 45%. Production data [2] confirms this."
        res_valid = eval_sources.verify_citations(valid_report, citation_map)
        self.assertTrue(res_valid["valid"])
        self.assertEqual(res_valid["cited_indexes"], [1, 2])
        self.assertEqual(res_valid["unused_indexes"], [3])
        self.assertEqual(res_valid["missing_indexes"], [])

        # Invalid text citing non-existent [99]
        invalid_report = "Autonomous agents scaled 10x [1], but unknown failure occurred [99]."
        res_invalid = eval_sources.verify_citations(invalid_report, citation_map)
        self.assertFalse(res_invalid["valid"])
        self.assertIn(99, res_invalid["missing_indexes"])
        self.assertTrue(len(res_invalid["errors"]) > 0)


class TestReadPage(unittest.TestCase):

    def test_clean_html(self):
        """Test stripping of tags, scripts, and whitespace collapsing."""
        html_content = """
        <html>
            <head>
                <style>body { color: red; }</style>
                <script>console.log("secret tracker");</script>
            </head>
            <body>
                <header>Navigation links</header>
                <h1>Research Title</h1>
                <p>Paragraph 1 with &amp; entity and <a href="#">link</a>.</p>
                <p>Paragraph 2 with data.</p>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        cleaned = read_page.clean_html(html_content)
        self.assertNotIn("console.log", cleaned)
        self.assertNotIn("body { color: red; }", cleaned)
        self.assertIn("Research Title", cleaned)
        self.assertIn("Paragraph 1 with & entity and link.", cleaned)
        self.assertIn("Paragraph 2 with data.", cleaned)

    def test_html_to_markdown_tables_standard(self):
        """Test conversion of standard HTML table with headers into Markdown table."""
        html_table = """
        <table>
            <thead>
                <tr><th>Benchmark</th><th>Score</th><th>Unit</th></tr>
            </thead>
            <tbody>
                <tr><td>Geekbench 6 Single</td><td>2850</td><td>pts</td></tr>
                <tr><td>Geekbench 6 Multi</td><td>8900</td><td>pts</td></tr>
            </tbody>
        </table>
        """
        tables = read_page.html_to_markdown_tables(html_table)
        self.assertEqual(len(tables), 1)
        md = tables[0]
        self.assertIn("| Benchmark | Score | Unit |", md)
        self.assertIn("|---|---|---|", md)
        self.assertIn("| Geekbench 6 Single | 2850 | pts |", md)
        self.assertIn("| Geekbench 6 Multi | 8900 | pts |", md)

    def test_tables_with_nested_tags_and_escaped_pipes(self):
        """Test extraction of table cells with nested markup, links, and pipe escaping."""
        html_table = """
        <table>
            <tr><th>Feature</th><th>Specification | Notes</th></tr>
            <tr>
                <td><a href="/specs"><strong>Architecture</strong></a></td>
                <td>8-core (4P + 4E) | 3.5GHz</td>
            </tr>
            <tr>
                <td>L3 Cache</td>
                <td><code>32 MB</code> shared</td>
            </tr>
        </table>
        """
        tables = read_page.html_to_markdown_tables(html_table)
        self.assertEqual(len(tables), 1)
        md = tables[0]
        # Verify pipes inside cells are escaped
        self.assertIn(r"Specification \| Notes", md)
        self.assertIn(r"8-core (4P + 4E) \| 3.5GHz", md)
        # Verify nested formatting stripped cleanly
        self.assertIn("| Architecture |", md)
        self.assertIn("| 32 MB shared |", md)

    def test_resilient_malformed_html_and_empty_inputs(self):
        """Test resilient handling of unclosed tags, malformed HTML, and empty inputs."""
        # Unclosed tags
        malformed = """
        <table>
            <tr><th>Col A<th>Col B &amp; C
            <tr><td>Val 1<td>Val 2
        </table>
        """
        tables = read_page.html_to_markdown_tables(malformed)
        self.assertEqual(len(tables), 1)
        self.assertIn("| Col A | Col B & C |", tables[0])
        self.assertIn("| Val 1 | Val 2 |", tables[0])

        # Empty / whitespace inputs
        self.assertEqual(read_page.html_to_markdown_tables(""), [])
        self.assertEqual(read_page.html_to_markdown_tables("   "), [])
        self.assertEqual(read_page.html_to_markdown_tables(None), [])
        self.assertEqual(read_page.html_to_markdown_tables("<html><body><p>No tables here</p></body></html>"), [])

        # Non-table layout snippets (e.g. empty 1x1 table)
        empty_table = "<table><tr><td></td></tr></table>"
        self.assertEqual(read_page.html_to_markdown_tables(empty_table), [])

    def test_extract_title_from_html(self):
        """Test title extraction from <title> tag and og:title meta tag."""
        # Standard <title>
        html1 = "<html><head><title>  NVIDIA H100 GPU Specs &amp; Benchmarks  </title></head></html>"
        self.assertEqual(read_page.extract_title_from_html(html1), "NVIDIA H100 GPU Specs & Benchmarks")

        # og:title meta fallback
        html2 = '<html><head><meta property="og:title" content="FDA Drug Trial Outcome 2026" /></head></html>'
        self.assertEqual(read_page.extract_title_from_html(html2), "FDA Drug Trial Outcome 2026")

        # Empty input
        self.assertEqual(read_page.extract_title_from_html(""), "")

    def test_extract_page_content_summary_failed_fetch(self):
        """Test extract_page_content_summary handles invalid URLs and failed fetches gracefully."""
        # Invalid scheme
        res = read_page.extract_page_content_summary("not-a-valid-url")
        self.assertFalse(res["success"])
        self.assertEqual(res["tables"], [])
        self.assertEqual(res["text"], "")

        # Non-routable IP with immediate timeout
        res2 = read_page.extract_page_content_summary("http://192.0.2.1:1/timeout", timeout=0.1)
        self.assertFalse(res2["success"])
        self.assertEqual(res2["tables"], [])

    def test_extract_page_content_summary_with_mock(self):
        """Test end-to-end extraction with mock HTML containing text and structured tables."""
        mock_html = """
        <html>
            <head><title>RTings OLED TV Laboratory Test Results</title></head>
            <body>
                <h1>Laboratory Test Overview</h1>
                <p>We tested panel brightness, black levels, and color accuracy.</p>
                <table>
                    <thead>
                        <tr><th>Test Parameter</th><th>Measured Value</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Peak 10% Window Brightness</td><td>1050 cd/m²</td></tr>
                        <tr><td>Native Contrast</td><td>Infinite:1</td></tr>
                    </tbody>
                </table>
                <p>Final verdict: Outstanding dark room performance.</p>
            </body>
        </html>
        """
        with patch("read_page.fetch_raw_page", return_value=(mock_html, "text/html", True)):
            summary = read_page.extract_page_content_summary("https://www.rtings.com/tv/reviews/test-oled")
            self.assertTrue(summary["success"])
            self.assertEqual(summary["title"], "RTings OLED TV Laboratory Test Results")
            self.assertEqual(len(summary["tables"]), 1)
            self.assertIn("| Test Parameter | Measured Value |", summary["tables"][0])
            self.assertIn("| Peak 10% Window Brightness | 1050 cd/m² |", summary["tables"][0])
            self.assertIn("We tested panel brightness", summary["text"])


class TestSecondOrderGapAnalysis(unittest.TestCase):

    def test_gap_analyst_schema_conformance(self):
        """Test that GAP_ANALYST_SCHEMA strictly conforms to second-order multi-hop reasoning requirements."""
        schema = gap_analysis.GAP_ANALYST_SCHEMA
        self.assertEqual(schema["type"], "object")
        self.assertIn("executive_critique", schema["properties"])
        self.assertIn("identified_gaps", schema["properties"])
        self.assertEqual(schema["required"], ["executive_critique", "identified_gaps"])

        items = schema["properties"]["identified_gaps"]["items"]
        item_props = items["properties"]
        self.assertIn("gap_type", item_props)
        self.assertIn("title", item_props)
        self.assertIn("description", item_props)
        self.assertIn("conflicting_claims", item_props)
        self.assertIn("targeted_query", item_props)
        self.assertIn("search_operator_type", item_props)
        self.assertIn("focus_entities", item_props)

        self.assertEqual(
            set(items["required"]),
            {"gap_type", "title", "description", "targeted_query"}
        )

        expected_gap_types = {"quantitative_deficit", "contradiction", "unverified_claim", "missing_subtopic"}
        self.assertEqual(set(item_props["gap_type"]["enum"]), expected_gap_types)

        expected_operator_types = {"exact_quote", "site_restricted", "filetype_pdf", "comparative_pair", "keyword_precision"}
        self.assertEqual(set(item_props["search_operator_type"]["enum"]), expected_operator_types)

    def test_detect_search_operator(self):
        """Test search operator detection across exact quote, site, filetype, comparative, and keyword queries."""
        # filetype:pdf / ext:pdf
        self.assertEqual(
            gap_analysis.detect_search_operator('filetype:pdf "H100 NVLink architecture whitepaper"'),
            "filetype_pdf"
        )
        self.assertEqual(
            gap_analysis.detect_search_operator('ext:pdf GLP-1 receptor agonist clinical trial phase 3'),
            "filetype_pdf"
        )

        # site_restricted
        self.assertEqual(
            gap_analysis.detect_search_operator('site:arxiv.org "mixture of experts" router balance'),
            "site_restricted"
        )
        self.assertEqual(
            gap_analysis.detect_search_operator('site:fda.gov "semaglutide" adverse events report'),
            "site_restricted"
        )

        # comparative_pair
        self.assertEqual(
            gap_analysis.detect_search_operator('"Groq LPU" vs "NVIDIA H100" time to first token latency'),
            "comparative_pair"
        )
        self.assertEqual(
            gap_analysis.detect_search_operator('OLED versus QD-OLED burn-in degradation lab test'),
            "comparative_pair"
        )
        self.assertEqual(
            gap_analysis.detect_search_operator('PostgreSQL compared to MySQL connection pooling overhead'),
            "comparative_pair"
        )

        # exact_quote
        self.assertEqual(
            gap_analysis.detect_search_operator('"speculative decoding" acceptance rate 70B parameter model'),
            "exact_quote"
        )

        # keyword_precision (default)
        self.assertEqual(
            gap_analysis.detect_search_operator('pharmacokinetics clearance half-life bioavailability percentage'),
            "keyword_precision"
        )
        self.assertEqual(
            gap_analysis.detect_search_operator(''),
            "keyword_precision"
        )
        self.assertEqual(
            gap_analysis.detect_search_operator(None),
            "keyword_precision"
        )

    def test_validate_gap_analysis_valid_payload(self):
        """Test validation of a fully conforming gap analysis response payload."""
        payload = {
            "executive_critique": "Evidence is robust on architecture but lacks empirical latency benchmarks and pricing curves.",
            "identified_gaps": [
                {
                    "gap_type": "quantitative_deficit",
                    "title": "Missing TTFT and Inter-token Latency Baselines",
                    "description": "Scouts report general speedup claims but lack exact p50/p99 millisecond benchmarks.",
                    "targeted_query": '"time to first token" latency benchmark p99 filetype:pdf',
                    "search_operator_type": "filetype_pdf",
                    "focus_entities": ["TTFT", "p99", "millisecond"]
                },
                {
                    "gap_type": "contradiction",
                    "title": "Manufacturer Throughput Claim vs Third-Party Lab Benchmark",
                    "description": "Vendor claims 3000 tokens/sec whereas independent tests report 1400 tokens/sec under load.",
                    "conflicting_claims": "Tier 1 vendor spec sheet states 3000 tps; Tier 2 MLPerf benchmark reports 1400 tps under 64 concurrency.",
                    "targeted_query": '"MLPerf Inference" benchmark results concurrency 64',
                    "search_operator_type": "exact_quote",
                    "focus_entities": ["MLPerf", "throughput"]
                },
                {
                    "gap_type": "unverified_claim",
                    "title": "Unsubstantiated Zero-Downtime Migration Claim",
                    "description": "Marketing claims instant failover without empirical proof of replication lag.",
                    "targeted_query": 'site:github.com failover replication lag issues',
                    "search_operator_type": "site_restricted"
                }
            ]
        }
        is_valid, errors = gap_analysis.validate_gap_analysis(payload)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_validate_gap_analysis_invalid_payloads(self):
        """Test validation failures on malformed or incomplete gap payloads."""
        # Missing executive_critique
        res1, errs1 = gap_analysis.validate_gap_analysis({"identified_gaps": []})
        self.assertFalse(res1)
        self.assertTrue(any("executive_critique" in e for e in errs1))

        # Empty identified_gaps
        res2, errs2 = gap_analysis.validate_gap_analysis({
            "executive_critique": "Solid overview.",
            "identified_gaps": []
        })
        self.assertFalse(res2)
        self.assertTrue(any("at least 1" in e for e in errs2))

        # Invalid gap_type enum value
        bad_gap = {
            "executive_critique": "Valid critique.",
            "identified_gaps": [
                {
                    "gap_type": "invalid_gap_category",
                    "title": "Title",
                    "description": "Desc",
                    "targeted_query": "query"
                }
            ]
        }
        res3, errs3 = gap_analysis.validate_gap_analysis(bad_gap)
        self.assertFalse(res3)
        self.assertTrue(any("Invalid gap_type" in e for e in errs3))

        # Invalid search_operator_type enum value
        bad_operator = {
            "executive_critique": "Valid critique.",
            "identified_gaps": [
                {
                    "gap_type": "quantitative_deficit",
                    "title": "Title",
                    "description": "Desc",
                    "targeted_query": "query",
                    "search_operator_type": "unsupported_operator"
                }
            ]
        }
        res4, errs4 = gap_analysis.validate_gap_analysis(bad_operator)
        self.assertFalse(res4)
        self.assertTrue(any("Invalid search_operator_type" in e for e in errs4))

        # Non-dict payload
        res5, errs5 = gap_analysis.validate_gap_analysis("not-a-dict")
        self.assertFalse(res5)

    def test_categorize_gaps(self):
        """Test grouping gaps into taxonomy buckets."""
        gaps = [
            {"gap_type": "quantitative_deficit", "title": "Deficit 1", "targeted_query": "q1"},
            {"gap_type": "contradiction", "title": "Contradiction 1", "targeted_query": "q2"},
            {"gap_type": "contradiction", "title": "Contradiction 2", "targeted_query": "q3"},
            {"gap_type": "unverified_claim", "title": "Claim 1", "targeted_query": "q4"},
            {"gap_type": "missing_subtopic", "title": "Subtopic 1", "targeted_query": "q5"},
        ]
        cats = gap_analysis.categorize_gaps(gaps)
        self.assertEqual(len(cats["quantitative_deficit"]), 1)
        self.assertEqual(len(cats["contradiction"]), 2)
        self.assertEqual(len(cats["unverified_claim"]), 1)
        self.assertEqual(len(cats["missing_subtopic"]), 1)

    def test_extract_precision_queries(self):
        """Test extraction of normalized precision scout targets and operator detection."""
        payload = {
            "executive_critique": "Need deeper quantitative analysis.",
            "identified_gaps": [
                {
                    "gap_type": "quantitative_deficit",
                    "title": "Energy Consumption Benchmark",
                    "description": "Need joules per token.",
                    "targeted_query": 'site:arxiv.org "joules per token" inference efficiency',
                    "focus_entities": ["joules", "energy"]
                },
                {
                    "gap_type": "contradiction",
                    "title": "Peak vs Sustained Throughput",
                    "description": "Specs dispute.",
                    "conflicting_claims": "Tier 1 vendor says 500 TFLOPS; Tier 2 says 320 TFLOPS sustained.",
                    "targeted_query": '"H100" vs "B200" sustained TFLOPS filetype:pdf',
                }
            ]
        }
        items = gap_analysis.extract_precision_queries(payload)
        self.assertEqual(len(items), 2)
        # Operator auto-detected correctly
        self.assertEqual(items[0]["search_operator_type"], "site_restricted")
        self.assertEqual(items[1]["search_operator_type"], "filetype_pdf")
        self.assertEqual(items[0]["focus_entities"], ["joules", "energy"])
        self.assertIn("500 TFLOPS", items[1]["conflicting_claims"])

    def test_build_gap_analyst_prompt(self):
        """Test prompt construction separating Wave 1 findings and Phase 1.6 deep primary tables."""
        dossier = [
            {
                "vector": "Hardware Architecture",
                "summary": "Initial breadth summary on accelerator interconnects.",
                "key_findings": ["Interconnect bandwidth is 900 GB/s", "Uses PCIe Gen 5"]
            },
            {
                "vector": "Deep Primary Page Evidence: [1] nvidia.com - H100 Architecture",
                "summary": "Verified Content Excerpt:\nFull whitepaper details.\n\n#### Extracted Primary Tables (1):\n| Spec | Value |\n| Memory | 80GB HBM3 |",
                "key_findings": ["Extracted 1 structured markdown data tables", "Primary page verified"]
            }
        ]
        citation_dist = {
            "total": 12,
            "tier_1_count": 6,
            "tier_1_pct": 50.0,
            "tier_2_count": 4,
            "tier_2_pct": 33.3,
            "tier_3_count": 2,
            "tier_3_pct": 16.7,
            "community_consensus_count": 2
        }

        prompt = gap_analysis.build_gap_analyst_prompt(
            topic="Modern AI Accelerators",
            evidence_dossier=dossier,
            citation_dist=citation_dist
        )

        self.assertIn("SECTION A: WAVE 1 BREADTH SCOUT FINDINGS", prompt)
        self.assertIn("SECTION B: PHASE 1.6 DEEP PRIMARY TABLES & EXCERPTS", prompt)
        self.assertIn("Hardware Architecture", prompt)
        self.assertIn("Extracted Primary Tables (1)", prompt)
        self.assertIn("Tier 1 (Official / Academic / Regulatory): 6 (50.0%)", prompt)
        self.assertIn("Quantitative Deficits", prompt)
        self.assertIn("Cross-Source Contradictions", prompt)
        self.assertIn("PRECISION QUERY GENERATION RULES", prompt)

    def test_evaluate_gap_resolution_and_formatting(self):
        """Test evaluating resolution status and formatting summary for Section 5."""
        gap_resolved = {
            "gap_type": "quantitative_deficit",
            "title": "Missing Latency Benchmarks",
            "description": "Lack p99 latency figures.",
            "targeted_query": '"latency benchmark" p99'
        }
        scout_res_resolved = {
            "summary": "Laboratory testing measured p99 latency at 12.4ms under 100 QPS load across 10,000 trials.",
            "key_findings": ["p99 latency measured at 12.4ms", "Tested under 100 QPS load"]
        }
        res1 = gap_analysis.evaluate_gap_resolution(gap_resolved, scout_res_resolved)
        self.assertEqual(res1["status"], "resolved")
        self.assertIn("p99 latency", res1["findings"][0])

        gap_contradiction = {
            "gap_type": "contradiction",
            "title": "Disputed Battery Degradation Claim",
            "description": "Vendor claims 90% retention after 1000 cycles, lab tests dispute.",
            "conflicting_claims": "Manufacturer claims 90% retention; independent lab reports 78% retention with heavy cell degradation.",
            "targeted_query": 'battery degradation cycle life test'
        }
        scout_res_contradiction = {
            "summary": "Test reports show persistent conflicting claims. Independent lab measurements contradict official vendor figures, showing mixed results and active dispute.",
            "key_findings": ["Independent labs found 78% capacity after 800 cycles", "Manufacturer disputes testing protocol"]
        }
        res2 = gap_analysis.evaluate_gap_resolution(gap_contradiction, scout_res_contradiction)
        self.assertEqual(res2["status"], "unresolved_discrepancy")

        # Format summary
        summary_md = gap_analysis.format_gap_resolution_summary([res1, res2])
        self.assertIn("Resolved Quantitative Deficits & Verified Claims: 1", summary_md)
        self.assertIn("Active Discrepancies & Contradictions: 1", summary_md)
        self.assertIn("Resolved Gaps & Empirical Clarifications", summary_md)
        self.assertIn("Unresolved Contradictions & Disputed Claims (MUST FEATURE IN SECTION 5)", summary_md)
        self.assertIn("Disputed Battery Degradation Claim", summary_md)


class TestWorkflowCompilation(unittest.TestCase):

    def test_workflow_file_compiles_with_top_level_await(self):
        """
        Verify that deep_research_workflow.py compiles cleanly under
        ast.PyCF_ALLOW_TOP_LEVEL_AWAIT flag as required by the OpenCode workflow runner.
        """
        workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
        self.assertTrue(workflow_path.exists(), f"Workflow file missing: {workflow_path}")

        with open(workflow_path, "r", encoding="utf-8") as f:
            code = f.read()

        try:
            compiled = compile(
                code,
                str(workflow_path),
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
            )
            self.assertIsNotNone(compiled)
        except SyntaxError as e:
            self.fail(f"Compilation failed for deep_research_workflow.py: {e}")

    def test_workflow_integrates_deep_page_inspection(self):
        """
        Verify deep_research_workflow.py explicitly executes Phase 1.6 deep primary inspection
        and utilizes read_page.extract_page_content_summary.
        """
        workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
        with open(workflow_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("Phase 1.6: Deep Primary Source Inspection", code)
        self.assertIn("read_page.extract_page_content_summary", code)
        self.assertIn("Deep Primary Page Evidence", code)

    def test_workflow_phase2_second_order_gap_analysis(self):
        """
        Verify deep_research_workflow.py configures Phase 2 Lead Gap Analyst (model='flash', type_name='self'),
        dispatches precision scouts under 'Wave 2 Gap Resolution: {title}', and passes
        gap resolution findings to the synthesizer for Section 5.
        """
        workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
        with open(workflow_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Schema and imports
        self.assertIn("import gap_analysis", code)
        self.assertIn("GAP_ANALYST_SCHEMA", code)
        self.assertIn('"executive_critique"', code)
        self.assertIn('"identified_gaps"', code)
        self.assertIn('"search_operator_type"', code)

        # Agent configuration
        self.assertIn('role="Lead Gap Analyst"', code)
        self.assertIn('model="flash"', code)
        self.assertIn('type_name="self"', code)

        # Wave 2 precision scout evidence tagging
        self.assertIn('"vector": f"Wave 2 Gap Resolution: {gap_title}"', code)
        self.assertIn("gap_analysis.evaluate_gap_resolution", code)
        self.assertIn("gap_analysis.format_gap_resolution_summary", code)

        # Synthesizer integration for Section 5
        self.assertIn("GAP RESOLUTION AUDIT (RESOLVED FINDINGS VS UNRESOLVED DISCREPANCIES FOR SECTION 5)", code)
        self.assertIn("Contradictions, Disputed Claims & Strategic Risks", code)

    def test_workflow_phase3_and_phase4_grounded_synthesis_integration(self):
        """
        Verify deep_research_workflow.py configures Phase 3 Lead Synthesizer and
        Phase 4 Critic agent with strict citation grounding, table embedding,
        gap resolution synthesis, and programmatic bibliography enforcement.
        """
        workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
        with open(workflow_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Phase 3 Lead Synthesizer
        self.assertIn('role="Lead Synthesizer"', code)
        self.assertIn('Decision Verdict', code)
        self.assertIn('Executive Narrative', code)
        self.assertIn('Comparative Matrix & Trade-Off Evaluation', code)
        self.assertIn('Dimension / Option | Specs & Capabilities | Pricing / TCO', code)
        self.assertIn('Zero Placeholders', code)

        # Phase 4 Critic / Verifier
        self.assertIn('role="Critic / Verifier"', code)
        self.assertIn('eval_sources.verify_citations', code)
        self.assertIn('eval_sources.ensure_report_bibliography', code)
        self.assertIn('AUDIT MANDATE', code)


class TestReportTemplateStructure(unittest.TestCase):
    """
    Unit tests for templates/report_template.md to verify comprehensive,
    publication-grade 7-section structure adapted for general intelligence research.
    """

    @classmethod
    def setUpClass(cls):
        template_path = SKILL_DIR / "templates" / "report_template.md"
        if not template_path.exists():
            raise FileNotFoundError(f"Missing template: {template_path}")
        with open(template_path, "r", encoding="utf-8") as f:
            cls.content = f.read()

    def test_all_seven_sections_present(self):
        """Verify all 7 top-level sections exist in proper sequential order."""
        sections = [
            "## 1. Executive Briefing",
            "## 2. Research Methodology & Evidence Scope",
            "## 3. Thematic Deep Dives",
            "## 4. Comparative Matrix & Trade-Off Evaluation",
            "## 5. Contradictions, Disputed Claims & Strategic Risks",
            "## 6. Strategic Outlook & Decision Playbook",
            "## 7. Reference Bibliography",
        ]
        last_pos = -1
        for s in sections:
            pos = self.content.find(s)
            self.assertNotEqual(pos, -1, f"Missing required section header: '{s}'")
            self.assertGreater(pos, last_pos, f"Section out of order: '{s}'")
            last_pos = pos

    def test_section_1_executive_briefing_elements(self):
        """Verify Section 1 contains Key Takeaways, Decision Verdict, and Executive Narrative."""
        sec1_idx = self.content.find("## 1. Executive Briefing")
        sec2_idx = self.content.find("## 2. Research Methodology & Evidence Scope")
        sec1_text = self.content[sec1_idx:sec2_idx]

        self.assertIn("### Key Takeaways", sec1_text)
        self.assertIn("### Decision Verdict", sec1_text)
        self.assertIn("### Executive Narrative", sec1_text)

    def test_section_2_methodology_and_evidence_scope(self):
        """Verify Section 2 contains 4-tier table, community consensus, and page inspection stats."""
        sec2_idx = self.content.find("## 2. Research Methodology & Evidence Scope")
        sec3_idx = self.content.find("## 3. Thematic Deep Dives")
        sec2_text = self.content[sec2_idx:sec3_idx]

        self.assertIn("Tier 1 (Primary Official)", sec2_text)
        self.assertIn("Tier 2 (Testing & Journalism)", sec2_text)
        self.assertIn("Tier 3 (Community Consensus)", sec2_text)
        self.assertIn("Tier 4 (General Web)", sec2_text)
        self.assertIn("{{COMMUNITY_SIGNALS}}", sec2_text)
        self.assertIn("{{PAGES_INSPECTED}}", sec2_text)
        self.assertIn("{{TABLES_EXTRACTED}}", sec2_text)

    def test_section_3_thematic_deep_dives_parameters_table(self):
        """Verify Section 3 includes quantitative benchmark parameters table schema."""
        sec3_idx = self.content.find("## 3. Thematic Deep Dives")
        sec4_idx = self.content.find("## 4. Comparative Matrix & Trade-Off Evaluation")
        sec3_text = self.content[sec3_idx:sec4_idx]

        self.assertIn("Component / Parameter", sec3_text)
        self.assertIn("Specification / Mechanism", sec3_text)
        self.assertIn("Observed Performance / Metric", sec3_text)
        self.assertIn("Source Citation", sec3_text)

    def test_section_4_comparative_matrix_table(self):
        """Verify Section 4 comparative matrix side-by-side GFM table schema."""
        sec4_idx = self.content.find("## 4. Comparative Matrix & Trade-Off Evaluation")
        sec5_idx = self.content.find("## 5. Contradictions, Disputed Claims & Strategic Risks")
        sec4_text = self.content[sec4_idx:sec5_idx]

        self.assertIn("Specs & Capabilities", sec4_text)
        self.assertIn("Pricing / TCO", sec4_text)
        self.assertIn("Benchmark Score / Throughput", sec4_text)
        self.assertIn("Community Consensus", sec4_text)
        self.assertIn("Best For", sec4_text)
        self.assertIn("Pareto Frontier", sec4_text)

    def test_section_5_contradictions_and_gap_resolution(self):
        """Verify Section 5 synthesizes Tier 1 vs Tier 2 vs Tier 3 tensions and resolved vs persistent gaps."""
        sec5_idx = self.content.find("## 5. Contradictions, Disputed Claims & Strategic Risks")
        sec6_idx = self.content.find("## 6. Strategic Outlook & Decision Playbook")
        sec5_text = self.content[sec5_idx:sec6_idx]

        self.assertIn("Tier 1 Official Claims", sec5_text)
        self.assertIn("Tier 2 Independent Test Lab Measurements", sec5_text)
        self.assertIn("Tier 3 Community Consensus", sec5_text)
        self.assertIn("Resolved Empirical Clarifications vs Persistent Discrepancies", sec5_text)
        self.assertIn("Strategic, Operational & Failure Mode Risks", sec5_text)

    def test_section_6_strategic_playbook_personas(self):
        """Verify Section 6 includes 12-24 month trajectory and persona recommendations."""
        sec6_idx = self.content.find("## 6. Strategic Outlook & Decision Playbook")
        sec7_idx = self.content.find("## 7. Reference Bibliography")
        sec6_text = self.content[sec6_idx:sec7_idx]

        self.assertIn("12–24 Month Trajectory", sec6_text)
        self.assertIn("For Technical Architects & Practitioners", sec6_text)
        self.assertIn("For Strategic Executives & Investors", sec6_text)
        self.assertIn("For Procurement & End-Users", sec6_text)

    def test_section_7_bibliography_format(self):
        """Verify Section 7 contains bibliography template placeholder and format specification."""
        sec7_idx = self.content.find("## 7. Reference Bibliography")
        sec7_text = self.content[sec7_idx:]

        self.assertIn("{{BIBLIOGRAPHY}}", sec7_text)
        self.assertIn("[N] **Title** — [URL](URL) (Tier X: Source Category: Domain)", sec7_text)


class TestBibliographyFormatting(unittest.TestCase):
    """
    Unit tests for eval_sources.format_bibliography_entry, format_bibliography,
    and ensure_report_bibliography.
    """

    def setUp(self):
        self.sample_citation_1 = {
            "index": 1,
            "title": "NIST AI Risk Management Framework 1.0",
            "url": "https://www.nist.gov/itl/ai-risk-management-framework",
            "domain": "www.nist.gov",
            "tier": 1,
            "source_category": "primary_official",
        }
        self.sample_citation_2 = {
            "index": 2,
            "title": "Reuters AI Infrastructure Cost Analysis",
            "url": "https://www.reuters.com/technology/ai-costs-2024",
            "domain": "www.reuters.com",
            "tier": 2,
            "source_category": "investigative_testing",
        }
        self.sample_citation_3 = {
            "index": 3,
            "title": "Community Post-Mortem on Distributed Caching Failures",
            "url": "https://reddit.com/r/sysadmin/comments/abc123/caching",
            "domain": "reddit.com",
            "tier": 3,
            "source_category": "community_consensus",
        }
        self.citation_map = {
            "citations": {
                1: self.sample_citation_1,
                2: self.sample_citation_2,
                3: self.sample_citation_3,
            }
        }

    def test_format_bibliography_entry(self):
        """Test formatting of individual bibliography entries matching required specification."""
        entry1 = eval_sources.format_bibliography_entry(self.sample_citation_1)
        expected1 = "[1] **NIST AI Risk Management Framework 1.0** — [https://www.nist.gov/itl/ai-risk-management-framework](https://www.nist.gov/itl/ai-risk-management-framework) (Tier 1: primary_official: www.nist.gov)"
        self.assertEqual(entry1, expected1)

        entry2 = eval_sources.format_bibliography_entry(self.sample_citation_2)
        expected2 = "[2] **Reuters AI Infrastructure Cost Analysis** — [https://www.reuters.com/technology/ai-costs-2024](https://www.reuters.com/technology/ai-costs-2024) (Tier 2: investigative_testing: www.reuters.com)"
        self.assertEqual(entry2, expected2)

        entry3 = eval_sources.format_bibliography_entry(self.sample_citation_3)
        expected3 = "[3] **Community Post-Mortem on Distributed Caching Failures** — [https://reddit.com/r/sysadmin/comments/abc123/caching](https://reddit.com/r/sysadmin/comments/abc123/caching) (Tier 3: community_consensus: reddit.com)"
        self.assertEqual(entry3, expected3)

    def test_format_bibliography_full(self):
        """Test formatting complete bibliography from citation map."""
        bib = eval_sources.format_bibliography(self.citation_map)
        lines = bib.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("[1] **NIST"))
        self.assertTrue(lines[1].startswith("[2] **Reuters"))
        self.assertTrue(lines[2].startswith("[3] **Community"))

    def test_format_bibliography_filtered_cited_only(self):
        """Test formatting bibliography with filter to only cited indices."""
        bib = eval_sources.format_bibliography(self.citation_map, cited_indexes={1, 3})
        lines = bib.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("[1]"))
        self.assertTrue(lines[1].startswith("[3]"))

    def test_ensure_report_bibliography_replaces_placeholder(self):
        """Test replacing placeholder in Section 7 with formatted bibliography entries."""
        report_with_placeholder = (
            "# Research Report\n\n"
            "## 1. Executive Briefing\n\nKey finding [1].\n\n"
            "## 7. Reference Bibliography\n\n"
            "{{BIBLIOGRAPHY}}\n"
        )
        finalized = eval_sources.ensure_report_bibliography(report_with_placeholder, self.citation_map)
        self.assertNotIn("{{BIBLIOGRAPHY}}", finalized)
        self.assertIn("## 7. Reference Bibliography", finalized)
        self.assertIn("[1] **NIST AI Risk Management Framework 1.0**", finalized)
        self.assertIn("[2] **Reuters AI Infrastructure Cost Analysis**", finalized)
        self.assertIn("[3] **Community Post-Mortem on Distributed Caching Failures**", finalized)

    def test_ensure_report_bibliography_appends_if_missing(self):
        """Test appending Section 7 if header was omitted."""
        report_without_bib = "# Research Report\n\n## 1. Executive Briefing\nKey finding [1]."
        finalized = eval_sources.ensure_report_bibliography(report_without_bib, self.citation_map)
        self.assertIn("## 7. Reference Bibliography", finalized)
        self.assertIn("[1] **NIST AI Risk Management Framework 1.0**", finalized)


class TestCitationVerificationMultiSection(unittest.TestCase):
    """
    End-to-end unit tests for citation verification on full multi-section reports.
    """

    def setUp(self):
        self.citation_map = {
            "citations": {
                1: {"index": 1, "title": "White House Executive Order", "url": "https://whitehouse.gov/eo", "tier": 1, "domain": "whitehouse.gov"},
                2: {"index": 2, "title": "Wirecutter Lab Benchmarks", "url": "https://wirecutter.com/lab", "tier": 2, "domain": "wirecutter.com"},
                3: {"index": 3, "title": "Hacker News Consensus", "url": "https://news.ycombinator.com/item?id=1", "tier": 3, "domain": "news.ycombinator.com"},
                4: {"index": 4, "title": "IEEE Standard 802.11", "url": "https://standards.ieee.org/802.11", "tier": 1, "domain": "standards.ieee.org"},
            }
        }

    def test_full_seven_section_report_valid(self):
        """Verify full 7-section report passes verification when all citations are grounded."""
        report = (
            "# Deep Research Report: Autonomous Systems\n\n"
            "## 1. Executive Briefing\n"
            "### Key Takeaways\n- Systems reduced latency by 34% [1].\n"
            "### Decision Verdict\nAdopt for mission-critical deployments [4].\n"
            "### Executive Narrative\nComprehensive analysis shows high reliability [1][2].\n\n"
            "## 2. Research Methodology & Evidence Scope\nIngested 4 sources across tiers.\n\n"
            "## 3. Thematic Deep Dives\n"
            "### 3.1 Architecture\nBandwidth peaked at 10 Gbps [4].\n\n"
            "## 4. Comparative Matrix & Trade-Off Evaluation\n"
            "Option A scored 94/100 in testing [2], while Option B scored 88/100 [3].\n\n"
            "## 5. Contradictions, Disputed Claims & Strategic Risks\n"
            "Manufacturer claimed 99.99% uptime [1], while lab testing observed 99.5% [2] and users reported brownouts [3].\n\n"
            "## 6. Strategic Outlook & Decision Playbook\n"
            "Expect multi-tenant hardware convergence in 2025 [1].\n\n"
            "## 7. Reference Bibliography\n"
            + eval_sources.format_bibliography(self.citation_map)
        )

        res = eval_sources.verify_citations(report, self.citation_map)
        self.assertTrue(res["valid"])
        self.assertEqual(res["missing_indexes"], [])
        self.assertEqual(set(res["cited_indexes"]), {1, 2, 3, 4})
        self.assertEqual(res["unused_indexes"], [])
        self.assertEqual(res["errors"], [])

    def test_report_with_unregistered_citation_fails(self):
        """Verify report with unregistered citation anchor [42] is flagged as invalid."""
        report = (
            "## 1. Executive Briefing\n"
            "Valid claim [1], but unregistered claim [42] causes failure."
        )
        res = eval_sources.verify_citations(report, self.citation_map)
        self.assertFalse(res["valid"])
        self.assertIn(42, res["missing_indexes"])
        self.assertTrue(any("42" in err for err in res["errors"]))

    def test_report_with_unresolved_placeholder_fails(self):
        """Verify report with unresolved placeholder [N] or [TODO] fails verification."""
        report = (
            "## 1. Executive Briefing\n"
            "Valid claim [1], but placeholder anchor [N] remains unpopulated."
        )
        res = eval_sources.verify_citations(report, self.citation_map)
        self.assertFalse(res["valid"])
        self.assertTrue(any("Unresolved citation placeholder '[N]'" in err for err in res["errors"]))

    def test_markdown_links_not_treated_as_citation_anchors(self):
        """Verify markdown links [Link Text](https://...) are not misparsed as numeric citations."""
        report = (
            "Review the [NIST Guidelines](https://nist.gov) for standards [1]. "
            "See [Executive Order 14110](https://whitehouse.gov) for regulation [1]."
        )
        res = eval_sources.verify_citations(report, self.citation_map)
        self.assertTrue(res["valid"])
        self.assertEqual(res["cited_indexes"], [1])


class TestWorkflowEndToEndMockExecution(unittest.TestCase):
    """
    End-to-end integration tests that exercise deep_research_workflow.py pipeline logic
    from Phase 0 through Phase 4 in a fully mocked offline environment.
    """

    @classmethod
    def setUpClass(cls):
        cls.workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
        with open(cls.workflow_path, "r", encoding="utf-8") as f:
            cls.workflow_code = f.read()
        cls.compiled_code = compile(
            cls.workflow_code,
            str(cls.workflow_path),
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        )

    def test_workflow_e2e_full_mock_execution(self):
        """
        Executes complete pipeline through Phase 0 to Phase 4 with mocked agents and pages.
        Verifies:
        - All 7 phases execute in sequence
        - Workspace markdown report is written
        - Conversation artifact is saved to <DEEP_RESEARCH_SCRATCH>/brain/<CONVERSATION_ID>/
        - Report has all 7 mandatory sections and passes citation verification.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            class MockAgent:
                def __init__(self, role=None, prompt=None, schema=None, **kwargs):
                    self.role = role or ""
                def __await__(self):
                    return self._run().__await__()
                async def _run(self):
                    role = self.role
                    if "Planner" in role:
                        return {
                            "domain_analysis": "Advanced Semiconductor Packaging & Interconnects",
                            "scoping_rationale": "Decomposing packaging physics, substrate availability, and yield economics.",
                            "vectors": [
                                {
                                    "id": "v_1",
                                    "name": "Substrate Capacity & CoWoS",
                                    "focus": "ABF substrate bottlenecks",
                                    "search_queries": ["ABF substrate shortage TSMC CoWoS"],
                                    "primary_source_types": ["semiconductor_consortium", "sec_10k_filings"],
                                },
                                {
                                    "id": "v_2",
                                    "name": "Thermal Dissipation & Warpage",
                                    "focus": "Microfluidic cooling and warpage mechanics",
                                    "search_queries": ["2.5D packaging silicon interposer warpage"],
                                    "primary_source_types": ["ieee_standards", "academic_journal"],
                                },
                                {
                                    "id": "v_3",
                                    "name": "Yield Economics & Test Coverage",
                                    "focus": "Known Good Die (KGD) test yield curves",
                                    "search_queries": ["KGD wafer probe defect density CoWoS"],
                                    "primary_source_types": ["testing_benchmark_lab", "investigative_journalism"],
                                },
                            ]
                        }
                    elif "Scout" in role:
                        return {
                            "vector": role,
                            "summary": (
                                f"Scout investigation for {role}. Primary consortium reports from "
                                "https://www.semiconductors.org/resources/packaging-report-2024/ note 14.8% yield loss, "
                                "while IEEE benchmarks at https://ieeexplore.ieee.org/document/9876543/ indicate 120W/cm2 thermal limits."
                            ),
                            "key_findings": [
                                "SIA documentation establishes that high-density substrate lead times remain extended at 42 weeks [https://www.semiconductors.org/resources/packaging-report-2024/].",
                                "IEEE measurements verify silicon interposer thermal dissipation limits of 120W/cm2 [https://ieeexplore.ieee.org/document/9876543/].",
                            ],
                            "sources": [
                                {"url": "https://www.semiconductors.org/resources/packaging-report-2024/", "title": "SIA Global Packaging Roadmap"},
                                {"url": "https://ieeexplore.ieee.org/document/9876543/", "title": "IEEE Transactions on Advanced Packaging"},
                            ]
                        }
                    elif "Gap Analyst" in role:
                        return {
                            "executive_critique": "Missing independent wafer-level test yield comparison between CoWoS-S and CoWoS-L.",
                            "identified_gaps": [
                                {
                                    "gap_type": "quantitative_deficit",
                                    "title": "CoWoS-S vs CoWoS-L Yield Discrepancy",
                                    "description": "Disputed yield figures between foundry marketing claims and independent test labs.",
                                    "targeted_query": "\"CoWoS-S\" vs \"CoWoS-L\" defect density yield comparison",
                                    "search_operator_type": "comparative_pair",
                                    "focus_entities": ["TSMC", "ASE Group", "Amkor"]
                                }
                            ]
                        }
                    elif "Synthesizer" in role:
                        return {
                            "report_markdown": (
                                "# Advanced Semiconductor Packaging: 2.5D and 3D Systems\n\n"
                                "## 1. Executive Briefing\n\n"
                                "### Key Takeaways\n"
                                "- High-density substrate lead times persist at 42 weeks according to SIA [1].\n"
                                "- Silicon interposer thermal limits cap sustained TDP at 120W/cm2 [2].\n\n"
                                "### Decision Verdict\n"
                                "Adopt 2.5D CoWoS-S for immediate production workloads, while establishing qualification pipelines for glass substrates [1].\n\n"
                                "### Executive Narrative\n"
                                "Advanced packaging has emerged as the principal scaling vector for high-performance AI accelerators. "
                                "Substrate availability and thermal dissipation govern deployment economics [1][2].\n\n"
                                "## 2. Research Methodology & Evidence Scope\n\n"
                                "Comprehensive investigation ingesting primary official registries, lab testing data, and engineering consensus.\n\n"
                                "## 3. Thematic Deep Dives\n\n"
                                "### Substrate Supply Dynamics\n"
                                "Analysis of ABF panel lines and yield curves [1].\n\n"
                                "| Component / Parameter | Specification / Mechanism | Observed Performance / Metric | Source Citation |\n"
                                "|---|---|---|---|\n"
                                "| Silicon Interposer | 2.5D Lithography Stitching | 3.3x Reticle Field | [1] |\n"
                                "| Thermal Flux | Micro-channel Liquid Cold Plate | 120 W/cm2 | [2] |\n\n"
                                "## 4. Comparative Matrix & Trade-Off Evaluation\n\n"
                                "| Dimension / Option | Specs & Capabilities | Pricing / TCO | Benchmark Score / Throughput | Community Consensus | Best For | Citations |\n"
                                "|---|---|---|---|---|---|---|\n"
                                "| CoWoS-S | Silicon interposer, 3.3x reticle | High ($2,200/wafer) | 1.8 TB/s interconnect | Industry standard | AI accelerators | [1] |\n"
                                "| CoWoS-L | RDL with LSI silicon bridges | Medium ($1,650/wafer) | 1.2 TB/s interconnect | Emerging adoption | Cost-sensitive HPC | [2] |\n\n"
                                "## 5. Contradictions, Disputed Claims & Strategic Risks\n\n"
                                "Cross-source tensions reveal a 4.2% discrepancy between manufacturer yield assertions and independent foundry teardowns [1][2].\n\n"
                                "## 6. Strategic Outlook & Decision Playbook\n\n"
                                "### Actionable Recommendations by Persona\n"
                                "- For Technical Architects: Lock interposer pinout specifications 18 months prior to tapeout [1].\n"
                                "- For Strategic Executives: Diversify substrate allocation across multiple Tier 1 suppliers [2].\n"
                                "- For Procurement Teams: Secure capacity reservation agreements with penalty clauses [1].\n\n"
                                "## 7. Reference Bibliography\n\n"
                                "[1] **SIA Global Packaging Roadmap** — [https://www.semiconductors.org/resources/packaging-report-2024/](https://www.semiconductors.org/resources/packaging-report-2024/) (Tier 1: primary_official: semiconductors.org)\n"
                                "[2] **IEEE Transactions on Advanced Packaging** — [https://ieeexplore.ieee.org/document/9876543/](https://ieeexplore.ieee.org/document/9876543/) (Tier 1: primary_official: ieeexplore.ieee.org)\n"
                            )
                        }
                    elif "Critic" in role:
                        return {
                            "approved": True,
                            "audit_notes": "Verified clean citations and complete 7-section structure.",
                            "corrected_report_markdown": (
                                "# Advanced Semiconductor Packaging: 2.5D and 3D Systems\n\n"
                                "## 1. Executive Briefing\n\n"
                                "### Key Takeaways\n"
                                "- High-density substrate lead times persist at 42 weeks according to SIA [1].\n"
                                "- Silicon interposer thermal limits cap sustained TDP at 120W/cm2 [2].\n\n"
                                "### Decision Verdict\n"
                                "Adopt 2.5D CoWoS-S for immediate production workloads, while establishing qualification pipelines for glass substrates [1].\n\n"
                                "### Executive Narrative\n"
                                "Advanced packaging has emerged as the principal scaling vector for high-performance AI accelerators. "
                                "Substrate availability and thermal dissipation govern deployment economics [1][2].\n\n"
                                "## 2. Research Methodology & Evidence Scope\n\n"
                                "Comprehensive investigation ingesting primary official registries, lab testing data, and engineering consensus.\n\n"
                                "## 3. Thematic Deep Dives\n\n"
                                "### Substrate Supply Dynamics\n"
                                "Analysis of ABF panel lines and yield curves [1].\n\n"
                                "| Component / Parameter | Specification / Mechanism | Observed Performance / Metric | Source Citation |\n"
                                "|---|---|---|---|\n"
                                "| Silicon Interposer | 2.5D Lithography Stitching | 3.3x Reticle Field | [1] |\n"
                                "| Thermal Flux | Micro-channel Liquid Cold Plate | 120 W/cm2 | [2] |\n\n"
                                "## 4. Comparative Matrix & Trade-Off Evaluation\n\n"
                                "| Dimension / Option | Specs & Capabilities | Pricing / TCO | Benchmark Score / Throughput | Community Consensus | Best For | Citations |\n"
                                "|---|---|---|---|---|---|---|\n"
                                "| CoWoS-S | Silicon interposer, 3.3x reticle | High ($2,200/wafer) | 1.8 TB/s interconnect | Industry standard | AI accelerators | [1] |\n"
                                "| CoWoS-L | RDL with LSI silicon bridges | Medium ($1,650/wafer) | 1.2 TB/s interconnect | Emerging adoption | Cost-sensitive HPC | [2] |\n\n"
                                "## 5. Contradictions, Disputed Claims & Strategic Risks\n\n"
                                "Cross-source tensions reveal a 4.2% discrepancy between manufacturer yield assertions and independent foundry teardowns [1][2].\n\n"
                                "## 6. Strategic Outlook & Decision Playbook\n\n"
                                "### Actionable Recommendations by Persona\n"
                                "- For Technical Architects: Lock interposer pinout specifications 18 months prior to tapeout [1].\n"
                                "- For Strategic Executives: Diversify substrate allocation across multiple Tier 1 suppliers [2].\n"
                                "- For Procurement Teams: Secure capacity reservation agreements with penalty clauses [1].\n\n"
                                "## 7. Reference Bibliography\n\n"
                                "[1] **SIA Global Packaging Roadmap** — [https://www.semiconductors.org/resources/packaging-report-2024/](https://www.semiconductors.org/resources/packaging-report-2024/) (Tier 1: primary_official: semiconductors.org)\n"
                                "[2] **IEEE Transactions on Advanced Packaging** — [https://ieeexplore.ieee.org/document/9876543/](https://ieeexplore.ieee.org/document/9876543/) (Tier 1: primary_official: ieeexplore.ieee.org)\n"
                            )
                        }
                    return {}

            mock_phases = []
            mock_logs = []
            conv_id = "test-e2e-conv-987"

            mock_globals = {
                "__file__": str(self.workflow_path),
                "__name__": "__main__",
                "args": {"topic": "Advanced Semiconductor Packaging and CoWoS Capacity", "depth": "deep"},
                "WORKSPACES": (tmpdir,),
                "CONVERSATION_ID": conv_id,
                "DEEP_RESEARCH_SCRATCH": tmpdir,
                "log": lambda *m: mock_logs.append(" ".join(str(x) for x in m)),
                "phase": lambda p: mock_phases.append(p),
                "agent": lambda **kw: MockAgent(**kw),
                "parallel": lambda items, fn: asyncio.gather(*[fn(x) for x in items]),
            }

            async def run():
                with patch("read_page.extract_page_content_summary", return_value={
                    "url": "https://www.semiconductors.org/resources/packaging-report-2024/",
                    "title": "SIA Global Packaging Roadmap",
                    "text": "Empirical excerpt detailing packaging yield curves and substrate limits.",
                    "tables": ["| Parameter | Specification |\n|---|---|\n| Substrate Lead Time | 42 weeks |"],
                    "success": True,
                }), patch("eval_sources.resolve_canonical_url", side_effect=lambda u, timeout=2.5: eval_sources.clean_url(u)):
                    coro = eval(self.compiled_code, mock_globals)
                    await coro

            asyncio.run(run())

            expected_phases = [
                "Phase 0: Dynamic Scoping & Adaptive Vector Planning",
                "Phase 1: Scouting - Wave 1 (Breadth Fan-out)",
                "Phase 1.5: Source Deduplication & Credibility Scoring",
                "Phase 1.6: Deep Primary Source Inspection",
                "Phase 2: Gap Analysis & Wave 2 Deep Dive",
                "Phase 3: Grounded Draft Synthesis",
                "Phase 4: Review & Validation Loop",
            ]
            self.assertEqual(mock_phases, expected_phases)

            expected_filename = "advanced-semiconductor-packaging-and-cowos-capacity-deep-research.md"
            workspace_report = Path(tmpdir) / expected_filename
            self.assertTrue(workspace_report.exists(), f"Workspace report missing: {workspace_report}")

            artifact_report = Path(tmpdir) / "brain" / conv_id / expected_filename
            self.assertTrue(artifact_report.exists(), f"Artifact report missing: {artifact_report}")

            report_content = workspace_report.read_text(encoding="utf-8")
            self.assertIn("## 1. Executive Briefing", report_content)
            self.assertIn("## 2. Research Methodology & Evidence Scope", report_content)
            self.assertIn("## 3. Thematic Deep Dives", report_content)
            self.assertIn("## 4. Comparative Matrix & Trade-Off Evaluation", report_content)
            self.assertIn("## 5. Contradictions, Disputed Claims & Strategic Risks", report_content)
            self.assertIn("## 6. Strategic Outlook & Decision Playbook", report_content)
            self.assertIn("## 7. Reference Bibliography", report_content)

            # Programmatic citation verification
            citation_map = eval_sources.build_citation_map([
                {"url": "https://www.semiconductors.org/resources/packaging-report-2024/", "title": "SIA Global Packaging Roadmap"},
                {"url": "https://ieeexplore.ieee.org/document/9876543/", "title": "IEEE Transactions on Advanced Packaging"},
            ], resolve_redirects=False)
            verification = eval_sources.verify_citations(report_content, citation_map)
            self.assertTrue(verification["valid"], f"Verification failed: {verification}")

    def test_workflow_e2e_resilience_empty_search_results(self):
        """
        Verifies workflow completes without unhandled exceptions when search scouts return
        empty sources, generating baseline deliverables in workspace and conversation artifacts.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            class MockEmptyAgent:
                def __init__(self, **kw): pass
                def __await__(self):
                    async def _run(): return {}
                    return _run().__await__()

            conv_id = "test-empty-conv-123"
            mock_globals = {
                "__file__": str(self.workflow_path),
                "__name__": "__main__",
                "args": {"topic": "Novel Superconductor Formulation", "depth": "deep"},
                "WORKSPACES": (tmpdir,),
                "CONVERSATION_ID": conv_id,
                "DEEP_RESEARCH_SCRATCH": tmpdir,
                "log": lambda *m: None,
                "phase": lambda p: None,
                "agent": lambda **kw: MockEmptyAgent(**kw),
                "parallel": lambda items, fn: asyncio.gather(*[fn(x) for x in items]),
            }

            async def run():
                with patch("read_page.extract_page_content_summary", return_value={"success": False}), \
                     patch("eval_sources.resolve_canonical_url", side_effect=lambda u, timeout=2.5: eval_sources.clean_url(u)):
                    coro = eval(self.compiled_code, mock_globals)
                    await coro

            asyncio.run(run())

            expected_filename = "novel-superconductor-formulation-deep-research.md"
            workspace_file = Path(tmpdir) / expected_filename
            self.assertTrue(workspace_file.exists(), "Workspace file should be generated even on empty results")
            artifact_file = Path(tmpdir) / "brain" / conv_id / expected_filename
            self.assertTrue(artifact_file.exists(), "Artifact file should be generated even on empty results")

            content = workspace_file.read_text(encoding="utf-8")
            self.assertIn("## 1. Executive Briefing", content)
            self.assertIn("## 7. Reference Bibliography", content)

    def test_workflow_e2e_resilience_malformed_agent_responses(self):
        """
        Verifies workflow handles malformed agent payloads (None, strings, corrupted structures)
        without unhandled crashes and delivers a structured report.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            class MockMalformedAgent:
                def __init__(self, **kw): pass
                def __await__(self):
                    async def _run(): return "CORRUPTED_STRING_RESPONSE"
                    return _run().__await__()

            conv_id = "test-malformed-conv-456"
            mock_globals = {
                "__file__": str(self.workflow_path),
                "__name__": "__main__",
                "args": {"topic": "Quantum Annealing Benchmarks", "depth": "deep"},
                "WORKSPACES": (tmpdir,),
                "CONVERSATION_ID": conv_id,
                "DEEP_RESEARCH_SCRATCH": tmpdir,
                "log": lambda *m: None,
                "phase": lambda p: None,
                "agent": lambda **kw: MockMalformedAgent(**kw),
                "parallel": lambda items, fn: asyncio.gather(*[fn(x) for x in items]),
            }

            async def run():
                with patch("read_page.extract_page_content_summary", return_value={"success": False}), \
                     patch("eval_sources.resolve_canonical_url", side_effect=lambda u, timeout=2.5: eval_sources.clean_url(u)):
                    coro = eval(self.compiled_code, mock_globals)
                    await coro

            asyncio.run(run())

            expected_filename = "quantum-annealing-benchmarks-deep-research.md"
            workspace_file = Path(tmpdir) / expected_filename
            self.assertTrue(workspace_file.exists())
            artifact_file = Path(tmpdir) / "brain" / conv_id / expected_filename
            self.assertTrue(artifact_file.exists())


if __name__ == "__main__":
    unittest.main()
