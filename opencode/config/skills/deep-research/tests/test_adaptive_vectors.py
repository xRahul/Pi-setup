#!/usr/bin/env python3
"""
Unit tests for adaptive domain detection, Phase 0 Lead Research Planner schema,
dynamic inquiry vector generation, vector validation, and resilient offline fallback planning.
"""

import ast
import sys
import unittest
from pathlib import Path

# Add scripts directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import adaptive_vectors

# Load functions from deep_research_workflow without triggering top-level await
def _load_workflow_module():
    workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
    tree = ast.parse(workflow_path.read_text(encoding="utf-8"))
    # Filter out top-level await nodes
    tree.body = [
        node for node in tree.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Await))
    ]
    code = compile(tree, str(workflow_path), "exec")
    namespace = {
        "__file__": str(workflow_path),
        "agent": None,
        "parallel": None,
        "log": lambda *a: None,
        "phase": lambda *a: None,
        "args": {},
    }
    exec(code, namespace)
    return namespace

_workflow_ns = _load_workflow_module()


class TestAdaptiveVectors(unittest.TestCase):

    def test_planner_schema_and_prompt_builder(self):
        """Verify Phase 0 Lead Research Planner schema and prompt generation contract."""
        schema = adaptive_vectors.PLANNER_SCHEMA
        self.assertIn("domain_analysis", schema["properties"])
        self.assertIn("scoping_rationale", schema["properties"])
        self.assertIn("vectors", schema["properties"])

        vec_item = schema["properties"]["vectors"]["items"]
        required_fields = ["id", "name", "focus", "search_queries", "primary_source_types"]
        for field in required_fields:
            self.assertIn(field, vec_item["properties"])
            self.assertIn(field, vec_item["required"])

        self.assertEqual(schema["properties"]["vectors"]["minItems"], 6)
        self.assertEqual(schema["properties"]["vectors"]["maxItems"], 8)

        # Test prompt builder
        prompt = adaptive_vectors.build_planner_prompt(
            topic="Authentic Neapolitan Pizza Fermentation",
            scope="Hydration and wood-fired oven heat dynamics",
            user_hints="Focus on AVPN standards and San Marzano tomatoes",
        )
        self.assertIn("Authentic Neapolitan Pizza Fermentation", prompt)
        self.assertIn("Hydration and wood-fired oven heat dynamics", prompt)
        self.assertIn("ZERO TEMPLATE BIAS", prompt)
        self.assertIn("AVPN standards", prompt)

    def test_vector_validation_logic(self):
        """Test strict validation of inquiry vectors."""
        # 1. Valid vectors
        valid_vectors = [
            {
                "id": f"vec_{i}",
                "name": f"Vector Title {i}",
                "focus": f"Detailed nuanced focus description for vector {i} covering empirical metrics.",
                "search_queries": [f"query alpha {i}", f"query beta {i}"],
                "primary_source_types": ["PubMed", "Peer-reviewed studies"],
            }
            for i in range(1, 7)
        ]
        is_valid, errors = adaptive_vectors.validate_vectors(valid_vectors)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

        # 2. Too few vectors (< 6)
        is_valid_few, errors_few = adaptive_vectors.validate_vectors(valid_vectors[:4])
        self.assertFalse(is_valid_few)
        self.assertTrue(any("Vector count must be between 6 and 8" in e for e in errors_few))

        # 3. Duplicate IDs
        dup_vectors = [dict(v) for v in valid_vectors]
        dup_vectors[1]["id"] = dup_vectors[0]["id"]
        is_valid_dup, errors_dup = adaptive_vectors.validate_vectors(dup_vectors)
        self.assertFalse(is_valid_dup)
        self.assertTrue(any("Duplicate vector id" in e for e in errors_dup))

        # 4. Short focus (< 20 chars)
        short_focus = [dict(v) for v in valid_vectors]
        short_focus[0]["focus"] = "Too short"
        is_valid_short, errors_short = adaptive_vectors.validate_vectors(short_focus)
        self.assertFalse(is_valid_short)
        self.assertTrue(any("at least 20 characters long" in e for e in errors_short))

        # 5. Missing or insufficient search queries (< 2)
        insufficient_queries = [dict(v) for v in valid_vectors]
        insufficient_queries[0]["search_queries"] = ["single query"]
        is_valid_q, errors_q = adaptive_vectors.validate_vectors(insufficient_queries)
        self.assertFalse(is_valid_q)
        self.assertTrue(any("at least 2 queries" in e for e in errors_q))

        # 6. Non-list input
        is_valid_nl, errors_nl = adaptive_vectors.validate_vectors("not-a-list")
        self.assertFalse(is_valid_nl)

    def test_out_of_distribution_topics_validation(self):
        """Test diverse out-of-distribution subject matter against vector validation."""
        test_scenarios = [
            # 1. Culinary
            ("Authentic Neapolitan Pizza Fermentation and Crust Chemistry", "Wood-fired oven heat dynamics and hydration"),
            # 2. Pharmacokinetics / Clinical
            ("GLP-1 Receptor Agonists for Obesity and Metabolic Syndrome: Semaglutide vs Tirzepatide", "Clinical trial endpoints, adverse events, and pricing"),
            # 3. Geopolitical / Maritime
            ("Taiwan Strait Maritime Shipping Traffic and Blockade Vulnerabilities", "Trade flows, military deterrence, and supply chain shocks"),
            # 4. Consumer hardware
            ("MacBook Pro M3 Max vs ThinkPad P1 Gen 6", "Benchmarks, battery endurance, and developer experience"),
            # 5. Acoustic panels / Materials physics
            ("Acoustic Panels for Home Studio Soundproofing: Fiberglass vs Rockwool", "NRC absorption coefficients and fire safety"),
        ]

        for topic, scope in test_scenarios:
            vectors = adaptive_vectors.generate_fallback_vectors(topic, scope)
            is_valid, errors = adaptive_vectors.validate_vectors(vectors)
            self.assertTrue(
                is_valid,
                f"Validation failed for topic '{topic}': {errors}"
            )
            self.assertTrue(6 <= len(vectors) <= 8)

            for v in vectors:
                self.assertTrue(len(v["id"]) > 0)
                self.assertTrue(len(v["name"]) > 0)
                self.assertTrue(len(v["focus"]) > 30)
                self.assertTrue(len(v["search_queries"]) >= 2)
                self.assertTrue(len(v["primary_source_types"]) >= 1)
                for q in v["search_queries"]:
                    self.assertIn(topic, q)

    def test_absence_of_software_architecture_jargon_in_non_tech_topics(self):
        """
        Verify that non-tech topics (culinary, pharma, geopolitics, materials, art)
        DO NOT receive software architecture jargon (CAP theorem, CVEs, microservices, etc.).
        """
        software_jargon = [
            "cap theorem",
            "cve",
            "garbage collection",
            "microservices",
            "kubernetes",
            "compiler design",
            "runtime memory",
            "sql query",
            "p50/p99 latency",
            "api endpoint",
            "byzantine fault",
        ]

        non_tech_topics = [
            ("Authentic Neapolitan Pizza Fermentation and Crust Chemistry", "Hydration and temperature"),
            ("GLP-1 Receptor Agonists for Obesity: Semaglutide vs Tirzepatide", "Pharmacokinetics and clinical trials"),
            ("Taiwan Strait Maritime Shipping Traffic and Blockade Vulnerabilities", "Trade flows and naval deterrence"),
            ("Acoustic Panels for Home Studio Soundproofing: Fiberglass vs Rockwool", "NRC sound absorption and fire rating"),
            ("Renaissance Fresco Preservation and Chemical Restoration Techniques", "Pigment stability and lime mortar"),
        ]

        for topic, scope in non_tech_topics:
            vectors = adaptive_vectors.generate_fallback_vectors(topic, scope)
            combined_text = " ".join(
                f"{v['name']} {v['focus']} {' '.join(v['search_queries'])}".lower()
                for v in vectors
            )
            for jargon in software_jargon:
                self.assertNotIn(
                    jargon,
                    combined_text,
                    f"Forbidden software jargon '{jargon}' found in non-tech topic '{topic}'!"
                )

    def test_domain_classification_precision(self):
        """Test accuracy of domain classifier across various real-world fields."""
        cases = [
            ("Sourdough bread fermentation and sourdough starter microbes", "culinary_food_science"),
            ("Phase 3 clinical trial endpoints for mRNA cancer vaccine", "biomedical_health"),
            ("Naval blockade scenarios in the Strait of Hormuz", "geopolitical_macro"),
            ("MacBook Pro M3 Max vs Dell XPS 16 benchmark shootout", "consumer_hardware"),
            ("Form 10-K balance sheet and quarterly earnings for Alphabet", "business_finance"),
            ("EU AI Act compliance obligations and statutory penalties", "policy_legal"),
            ("Distributed Raft consensus protocol leader election", "technology_architecture"),
            ("7-day travel itinerary for Iceland Ring Road in summer", "lifestyle_travel_general"),
            ("Acoustic dampening properties of porous open-cell foam", "universal_inquiry"),
        ]

        for topic, expected_dom in cases:
            detected = adaptive_vectors.detect_domain(topic)
            self.assertEqual(
                detected,
                expected_dom,
                f"Topic '{topic}' classified as '{detected}', expected '{expected_dom}'"
            )

    def test_deep_technology_topic_maintains_rigorous_technical_vectors(self):
        """Verify that deep systems topics still receive rigorous technical vectors."""
        topic = "Distributed Raft Consensus Protocol Internals and Log Compaction"
        scope = "Leader election, partition recovery, and p99 latency scaling"
        vecs = adaptive_vectors.generate_fallback_vectors(topic, scope)
        self.assertEqual(vecs[0]["domain"], "technology_architecture")

        ids = [v["id"] for v in vecs]
        self.assertIn("architecture_protocols", ids)
        self.assertIn("empirical_benchmarks", ids)
        self.assertIn("operational_tradeoffs", ids)
        self.assertIn("security_threat_model", ids)

    def test_workflow_backward_compatibility(self):
        """Verify workflow generate_default_storm_vectors delegates cleanly to fallback planner."""
        vecs = _workflow_ns["generate_default_storm_vectors"](
            topic="Sourdough Bread Making Chemistry",
            scope="Fermentation time and crumb structure"
        )
        self.assertTrue(len(vecs) >= 6)
        self.assertEqual(vecs[0]["domain"], "culinary_food_science")
        is_valid, errors = adaptive_vectors.validate_vectors(vecs)
        self.assertTrue(is_valid, f"Workflow vectors invalid: {errors}")

    def test_workflow_file_compiles_with_top_level_await(self):
        """Verify deep_research_workflow.py compiles cleanly under PyCF_ALLOW_TOP_LEVEL_AWAIT."""
        workflow_path = SCRIPTS_DIR / "deep_research_workflow.py"
        self.assertTrue(workflow_path.exists())
        code = workflow_path.read_text(encoding="utf-8")
        try:
            compiled = compile(code, str(workflow_path), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            self.assertIsNotNone(compiled)
        except SyntaxError as e:
            self.fail(f"Compilation failed for deep_research_workflow.py: {e}")


if __name__ == "__main__":
    unittest.main()
