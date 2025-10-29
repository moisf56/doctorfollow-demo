"""
Integration Test: Modern KG with DoctorFollow API
Tests the new LLM-generated graph on real Turkish medical queries
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_3"))

import json
import time
from typing import Dict, List
from modern_kg_expander import ModernKGExpander
from neo4j_store import Neo4jStore
from config import settings


def load_turkish_queries() -> List[Dict]:
    """Load Turkish test queries"""
    query_file = Path(__file__).parent.parent / "data" / "turkish_queries.json"

    if not query_file.exists():
        print(f"Warning: {query_file} not found")
        # Return sample queries
        return [
            {
                "id": "test_1",
                "query_turkish": "PPHN tedavisi nedir?",
                "query_english": "What is the treatment for PPHN?",
                "category": "treatment"
            },
            {
                "id": "test_2",
                "query_turkish": "Prematüre bebeklerde solunum sorunları nelerdir?",
                "query_english": "What are respiratory problems in premature infants?",
                "category": "symptoms"
            },
            {
                "id": "test_3",
                "query_turkish": "Yenidoğan sepsisi nasıl tedavi edilir?",
                "query_english": "How is neonatal sepsis treated?",
                "category": "treatment"
            }
        ]

    with open(query_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("evaluation_queries", [])[:5]  # First 5 queries


def test_kg_enrichment(
    neo4j: Neo4jStore,
    expander: ModernKGExpander,
    query: str,
    strategy: str = "auto"
) -> Dict:
    """
    Test KG enrichment for a single query

    Returns:
        dict with timing, context length, and content
    """
    start_time = time.time()

    # Mock chunks (in real API, these come from hybrid retrieval)
    mock_chunks = [
        {
            "chunk_id": "mock_1",
            "text": "Medical text related to query..."
        }
    ]

    # Get KG enrichment
    kg_context = expander.expand_with_graph(
        query,
        mock_chunks,
        max_hops=2,
        strategy=strategy
    )

    elapsed = time.time() - start_time

    return {
        "query": query,
        "strategy": strategy,
        "elapsed_ms": round(elapsed * 1000, 2),
        "context_length": len(kg_context) if kg_context else 0,
        "context_preview": kg_context[:300] if kg_context else "(empty)",
        "has_context": bool(kg_context)
    }


def print_section(title):
    """Print formatted section"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def run_integration_tests():
    """Run full integration test suite"""
    print("=" * 80)
    print("  DOCTORFOLLOW API INTEGRATION TEST")
    print("  Testing Modern KG Expander with Real Queries")
    print("=" * 80)

    # Connect to Neo4j
    print("\n[1/4] Connecting to Neo4j...")
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    print("✓ Connected")

    # Initialize expander
    print("\n[2/4] Initializing Modern KG Expander...")
    expander = ModernKGExpander(neo4j)
    print("✓ Initialized")

    # Load queries
    print("\n[3/4] Loading Turkish test queries...")
    queries = load_turkish_queries()
    print(f"✓ Loaded {len(queries)} queries")

    # Run tests
    print("\n[4/4] Running tests...")
    print_section("TEST RESULTS")

    results = []

    for i, query_data in enumerate(queries, 1):
        query_en = query_data.get("query_english", query_data.get("query_turkish", ""))
        category = query_data.get("category", "unknown")

        print(f"\n[Query {i}/{len(queries)}]")
        print(f"Category: {category}")
        print(f"Query: {query_en}")
        print("-" * 60)

        # Test with auto strategy
        result = test_kg_enrichment(neo4j, expander, query_en, strategy="auto")
        results.append(result)

        # Print result
        if result["has_context"]:
            print(f"✓ KG enrichment successful")
            print(f"  Strategy: {result['strategy']}")
            print(f"  Elapsed: {result['elapsed_ms']}ms")
            print(f"  Context length: {result['context_length']} chars")
            print(f"  Preview: {result['context_preview']}...")
        else:
            print(f"✗ No KG context generated")
            print(f"  Elapsed: {result['elapsed_ms']}ms")

    # Summary
    print_section("SUMMARY")

    successful = sum(1 for r in results if r["has_context"])
    total = len(results)
    avg_latency = sum(r["elapsed_ms"] for r in results) / total if total > 0 else 0
    avg_context_len = sum(r["context_length"] for r in results) / total if total > 0 else 0

    print(f"Total queries: {total}")
    print(f"Successful KG enrichments: {successful} ({successful/total*100:.1f}%)")
    print(f"Average latency: {avg_latency:.2f}ms")
    print(f"Average context length: {avg_context_len:.0f} chars")

    # Per-category breakdown
    categories = {}
    for result in results:
        cat = "unknown"
        for q in queries:
            if result["query"] in q.get("query_english", ""):
                cat = q.get("category", "unknown")
                break

        if cat not in categories:
            categories[cat] = {"total": 0, "successful": 0}
        categories[cat]["total"] += 1
        if result["has_context"]:
            categories[cat]["successful"] += 1

    print("\nBy category:")
    for cat, stats in categories.items():
        success_rate = stats["successful"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat}: {stats['successful']}/{stats['total']} ({success_rate:.1f}%)")

    # Strategy comparison
    print_section("STRATEGY COMPARISON")

    test_query = queries[0].get("query_english", queries[0].get("query_turkish", ""))
    print(f"Test query: {test_query}\n")

    strategies = ["local", "global", "hybrid"]
    strategy_results = {}

    for strategy in strategies:
        result = test_kg_enrichment(neo4j, expander, test_query, strategy=strategy)
        strategy_results[strategy] = result

        print(f"[{strategy.upper()}]")
        print(f"  Latency: {result['elapsed_ms']}ms")
        print(f"  Context length: {result['context_length']} chars")
        print(f"  Has context: {'✓' if result['has_context'] else '✗'}")

    # Recommendations
    print_section("RECOMMENDATIONS")

    if successful / total >= 0.8:
        print("✓ EXCELLENT: KG enrichment working well (≥80% success rate)")
        print("  → Ready for production deployment")
    elif successful / total >= 0.5:
        print("⚠ GOOD: KG enrichment working moderately (50-80% success rate)")
        print("  → Consider improving entity extraction")
    else:
        print("✗ NEEDS WORK: Low KG enrichment rate (<50%)")
        print("  → Check entity names in graph")
        print("  → Verify query terms match graph entities")

    if avg_latency < 1000:
        print(f"✓ FAST: Average latency {avg_latency:.0f}ms < 1s")
    elif avg_latency < 2000:
        print(f"⚠ ACCEPTABLE: Average latency {avg_latency:.0f}ms (1-2s)")
    else:
        print(f"✗ SLOW: Average latency {avg_latency:.0f}ms > 2s")
        print("  → Consider reducing max_hops or limiting entity count")

    # Next steps
    print("\nNext steps:")
    print("1. If results look good, update iteration_3/rag_v3.py to use modern_kg_expander")
    print("2. Test end-to-end with API server")
    print("3. A/B test: old vs new on real Turkish queries")
    print("4. Monitor production performance")

    # Cleanup
    neo4j.close()
    print("\n✓ Test complete!")


if __name__ == "__main__":
    try:
        run_integration_tests()
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
