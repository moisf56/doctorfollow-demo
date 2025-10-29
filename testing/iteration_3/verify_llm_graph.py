"""
Quick verification: Can we access the LLM-generated graph?
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from neo4j_store import Neo4jStore
from config import settings


def verify_llm_graph():
    """Verify we can access the graph created by LLM Graph Builder GUI"""

    print("=" * 80)
    print("  VERIFYING ACCESS TO LLM-GENERATED GRAPH")
    print("=" * 80)

    # Connect
    print("\n[1] Connecting to Neo4j...")
    print(f"  URI: {settings.NEO4J_URI}")

    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    print("  ✓ Connected!")

    with neo4j.driver.session() as session:
        # Test 1: Total nodes
        print("\n[2] Checking total nodes...")
        result = session.run("MATCH (n) RETURN count(n) AS total").single()
        total_nodes = result["total"]
        print(f"  ✓ Total nodes: {total_nodes}")

        if total_nodes == 0:
            print("\n  ✗ ERROR: No nodes found!")
            print("  This means either:")
            print("    1. The LLM Graph Builder wrote to a different database")
            print("    2. The graph hasn't been created yet")
            print("    3. Connection settings are incorrect")
            return False

        # Test 2: Node types from your screenshots
        print("\n[3] Checking for 'Condition' nodes (from your screenshot)...")
        result = session.run("""
            MATCH (n:Condition)
            RETURN count(n) AS count
        """).single()
        condition_count = result["count"]
        print(f"  ✓ Condition nodes: {condition_count}")

        if condition_count == 0:
            print("  ⚠ Warning: No 'Condition' nodes found")
            print("  Checking what node types exist...")
            result = session.run("""
                MATCH (n)
                RETURN DISTINCT labels(n)[0] AS type, count(n) AS count
                ORDER BY count DESC
                LIMIT 10
            """)
            print("\n  Available node types:")
            for record in result:
                print(f"    - {record['type']}: {record['count']}")

        # Test 3: Check for SIMILAR relationships (semantic links)
        print("\n[4] Checking for SIMILAR relationships (from your screenshot)...")
        result = session.run("""
            MATCH ()-[r:SIMILAR]->()
            RETURN count(r) AS count
        """).single()
        similar_count = result["count"]
        print(f"  ✓ SIMILAR relationships: {similar_count}")

        if similar_count == 0:
            print("  ⚠ Warning: No SIMILAR relationships found")

        # Test 4: Total relationships
        print("\n[5] Checking total relationships...")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN count(r) AS total
        """).single()
        total_rels = result["total"]
        print(f"  ✓ Total relationships: {total_rels}")

        # Test 5: Sample entity
        print("\n[6] Getting a sample entity...")
        result = session.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL
            RETURN n.name AS name, labels(n)[0] AS type
            LIMIT 1
        """).single()

        if result:
            entity_name = result["name"]
            entity_type = result["type"]
            print(f"  ✓ Sample entity: '{entity_name}' ({entity_type})")

            # Test 6: Can we query relationships?
            print(f"\n[7] Checking relationships for '{entity_name}'...")
            result = session.run("""
                MATCH (e)-[r]-(related)
                WHERE e.name = $name
                RETURN type(r) AS rel_type, related.name AS target, labels(related)[0] AS target_type
                LIMIT 5
            """, name=entity_name)

            relationships = list(result)
            if relationships:
                print(f"  ✓ Found {len(relationships)} relationships:")
                for rel in relationships:
                    print(f"    - {rel['rel_type']} → {rel['target']} ({rel['target_type']})")
            else:
                print(f"  ⚠ No relationships found for this entity")

        # Summary
        print("\n" + "=" * 80)
        print("  SUMMARY")
        print("=" * 80)

        if total_nodes > 0:
            print("\n✓ SUCCESS: Your neo4j_store.py CAN access the LLM-generated graph!")
            print(f"\nGraph statistics:")
            print(f"  - Nodes: {total_nodes}")
            print(f"  - Relationships: {total_rels}")
            if condition_count > 0:
                print(f"  - Condition entities: {condition_count}")
            if similar_count > 0:
                print(f"  - Semantic links (SIMILAR): {similar_count}")

            print("\n✓ You're ready to use modern_kg_expander.py!")
            print("\nNext steps:")
            print("  1. Run: test_modern_kg.py")
            print("  2. Then: test_on_api.py")
            return True
        else:
            print("\n✗ PROBLEM: No nodes found in the database")
            print("\nTroubleshooting:")
            print("  1. Check if you're connected to the correct Neo4j instance")
            print("  2. Verify the LLM Graph Builder successfully created the graph")
            print("  3. Check Neo4j Browser to see if data exists")
            return False

    neo4j.close()


if __name__ == "__main__":
    try:
        success = verify_llm_graph()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
