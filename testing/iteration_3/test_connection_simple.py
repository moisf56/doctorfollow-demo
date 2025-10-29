"""
Simple connection test - no Unicode characters
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from neo4j_store import Neo4jStore
from config import settings


print("="*80)
print("NEO4J CONNECTION TEST")
print("="*80)

print(f"\nURI: {settings.NEO4J_URI}")
print(f"User: {settings.NEO4J_USER}")

try:
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    print("[OK] Connected successfully!")

    with neo4j.driver.session() as session:
        # Test 1: Count nodes
        result = session.run("MATCH (n) RETURN count(n) AS total").single()
        total = result["total"]
        print(f"[OK] Total nodes: {total}")

        if total == 0:
            print("\n[WARNING] No nodes found in database")
            print("This is a fresh database. Did you upload data to LLM Graph Builder GUI?")
        else:
            # Test 2: Node types
            print("\nNode types:")
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS type, count(n) AS count
                ORDER BY count DESC
                LIMIT 5
            """)
            for record in result:
                print(f"  - {record['type']}: {record['count']}")

            # Test 3: Relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS total").single()
            total_rels = result["total"]
            print(f"\n[OK] Total relationships: {total_rels}")

    neo4j.close()
    print("\n[SUCCESS] All tests passed!")

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
