"""
Test Script for Modern KG Expander
Validates your LLM-generated graph and tests modern query enhancement strategies
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from neo4j_store import Neo4jStore
from modern_kg_expander import ModernKGExpander
from config import settings
import json


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_graph_statistics(neo4j: Neo4jStore):
    """Test 1: Verify your new LLM-generated graph structure"""
    print_section("TEST 1: Graph Statistics (From LLM Graph Builder)")

    with neo4j.driver.session() as session:
        # Total nodes
        result = session.run("MATCH (n) RETURN count(n) AS total").single()
        total_nodes = result["total"]
        print(f"✓ Total Nodes: {total_nodes}")

        # Nodes by type
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS type, count(n) AS count
            ORDER BY count DESC
            LIMIT 10
        """)
        print("\n✓ Top 10 Node Types:")
        for record in result:
            print(f"  - {record['type']}: {record['count']}")

        # Total relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) AS total").single()
        total_rels = result["total"]
        print(f"\n✓ Total Relationships: {total_rels}")

        # Relationships by type
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS count
            ORDER BY count DESC
            LIMIT 10
        """)
        print("\n✓ Top 10 Relationship Types:")
        for record in result:
            print(f"  - {record['rel_type']}: {record['count']}")


def test_entity_search(expander: ModernKGExpander):
    """Test 2: Entity search and extraction"""
    print_section("TEST 2: Entity Recognition & Search")

    test_cases = [
        ("What is the treatment for PPHN?", "Should find 'PPHN' entity"),
        ("Ampicillin dose for neonates", "Should find 'ampicillin' entity"),
        ("respiratory distress management", "Should find 'respiratory distress' entity"),
    ]

    for query, expected in test_cases:
        print(f"\nQuery: '{query}'")
        print(f"Expected: {expected}")

        # Extract entities
        entities = expander._extract_entity_names(query, [])
        if entities:
            print(f"✓ Found entities: {entities}")
        else:
            print("✗ No entities found")


def test_local_search(expander: ModernKGExpander, neo4j: Neo4jStore):
    """Test 3: Local search (entity-focused)"""
    print_section("TEST 3: Local Search (Entity-Focused)")

    # Find a real entity from your graph
    with neo4j.driver.session() as session:
        result = session.run("""
            MATCH (n:Condition)
            WHERE n.name IS NOT NULL
            RETURN n.name AS name
            LIMIT 1
        """).single()

        if not result:
            print("✗ No Condition nodes found in graph")
            return

        entity_name = result["name"]
        print(f"\nTesting with entity: '{entity_name}'")

    # Test neighborhood traversal
    context = expander._traverse_entity_neighborhood(entity_name, max_hops=2)

    if context:
        print(f"✓ Found context ({len(context)} chars):")
        print("-" * 60)
        print(context)
        print("-" * 60)
    else:
        print(f"✗ No context found for {entity_name}")


def test_semantic_search(expander: ModernKGExpander, neo4j: Neo4jStore):
    """Test 4: Semantic search (SIMILAR relationships)"""
    print_section("TEST 4: Semantic Search (SIMILAR Relationships)")

    # Check if SIMILAR relationships exist
    with neo4j.driver.session() as session:
        result = session.run("""
            MATCH ()-[s:SIMILAR]->()
            RETURN count(s) AS count
        """).single()

        similar_count = result["count"]
        print(f"✓ Total SIMILAR relationships: {similar_count}")

        if similar_count == 0:
            print("⚠ No SIMILAR relationships found. Semantic search will be limited.")
            return

        # Get a sample chunk with SIMILAR relationships
        result = session.run("""
            MATCH (c:Chunk)-[s:SIMILAR]->(related:Chunk)
            RETURN c.id AS chunk_id, c.text AS text
            LIMIT 1
        """).single()

        if not result:
            print("✗ No chunks with SIMILAR relationships found")
            return

        chunk_id = result["chunk_id"]
        chunk_text = result["text"][:100] + "..."

        print(f"\nTesting with chunk: '{chunk_text}'")

    # Find similar chunks
    similar_chunks = expander._find_similar_chunks(chunk_id, limit=3)

    if similar_chunks:
        print(f"✓ Found {len(similar_chunks)} similar chunks:")
        for i, chunk in enumerate(similar_chunks, 1):
            print(f"\n  [{i}] {chunk['text'][:150]}...")
    else:
        print("✗ No similar chunks found")


def test_full_pipeline(expander: ModernKGExpander):
    """Test 5: Full pipeline with real medical query"""
    print_section("TEST 5: Full Pipeline (Real Medical Query)")

    # Test queries from your Turkish dataset
    test_queries = [
        "What is the treatment for persistent pulmonary hypertension?",
        "What are the complications of prematurity?",
        "How is respiratory distress syndrome diagnosed?",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 60)

        # Mock retrieved chunks (in real usage, these come from hybrid retrieval)
        mock_chunks = [
            {"chunk_id": "chunk_1", "text": "Sample medical text about the condition..."},
        ]

        # Test with auto strategy detection
        context = expander.expand_with_graph(
            query,
            mock_chunks,
            max_hops=2,
            strategy="auto"
        )

        if context:
            print(f"✓ Generated context ({len(context)} chars)")
            print(context[:500] + "..." if len(context) > 500 else context)
        else:
            print("✗ No KG context generated")


def test_strategy_comparison(expander: ModernKGExpander):
    """Test 6: Compare different strategies"""
    print_section("TEST 6: Strategy Comparison (Local vs Global vs Hybrid)")

    query = "What are neonatal respiratory complications?"
    mock_chunks = [{"chunk_id": "chunk_1", "text": "Neonatal complications include..."}]

    strategies = ["local", "global", "hybrid"]

    for strategy in strategies:
        print(f"\n[Strategy: {strategy}]")
        print("-" * 60)

        context = expander.expand_with_graph(
            query,
            mock_chunks,
            strategy=strategy
        )

        if context:
            print(f"✓ Context generated ({len(context)} chars)")
            print(context[:300] + "...")
        else:
            print(f"✗ No context for {strategy} strategy")


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print("  MODERN KG EXPANDER TEST SUITE")
    print("  Testing LLM-generated graph from Neo4j Graph Builder")
    print("=" * 80)

    # Connect to Neo4j
    print("\nConnecting to Neo4j...")
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    print("✓ Connected to Neo4j")

    # Initialize expander
    expander = ModernKGExpander(neo4j)
    print("✓ Initialized Modern KG Expander")

    try:
        # Run tests
        test_graph_statistics(neo4j)
        test_entity_search(expander)
        test_local_search(expander, neo4j)
        test_semantic_search(expander, neo4j)
        test_full_pipeline(expander)
        test_strategy_comparison(expander)

        # Summary
        print_section("TEST SUMMARY")
        print("✓ All tests completed!")
        print("\nNext steps:")
        print("1. Review the graph statistics - do they match your screenshots?")
        print("2. Check if entity extraction is working correctly")
        print("3. Verify that local/global search strategies return useful context")
        print("4. Test with your Turkish queries using the updated RAG v3")

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.close()
        print("\n✓ Neo4j connection closed")


if __name__ == "__main__":
    run_all_tests()
