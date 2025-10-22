"""
Quick script to build the Knowledge Graph from indexed documents
Run this ONCE after you've indexed your medical PDFs
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import ElasticsearchStore
from neo4j_store import Neo4jStore
from medical_kg_builder import MedicalKGBuilder

def main():
    print("="*80)
    print("BUILDING MEDICAL KNOWLEDGE GRAPH")
    print("="*80)
    print()

    # Get credentials
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    print("Initializing connections...")
    print(f"  Neo4j: {neo4j_uri}")
    print()

    # Initialize stores
    print("[1/4] Connecting to Elasticsearch...")
    opensearch = ElasticsearchStore()

    print("[2/4] Connecting to Neo4j...")
    neo4j = Neo4jStore(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    print("[3/4] Initializing KG Builder...")
    kg_builder = MedicalKGBuilder(
        opensearch_store=opensearch,
        neo4j_store=neo4j
    )

    print("\n" + "="*80)
    print("[4/4] BUILDING KNOWLEDGE GRAPH")
    print("="*80)
    print()
    print("This will:")
    print("  1. Extract medical entities from your indexed documents")
    print("  2. Identify relationships between entities")
    print("  3. Populate Neo4j with entities and relationships")
    print()
    print("⚠️  This may take 5-15 minutes depending on document size...")
    print()

    # Build the graph
    try:
        kg_builder.build_graph(
            limit_chunks=500  # Process up to 500 chunks
        )

        print("\n" + "="*80)
        print("✅ KNOWLEDGE GRAPH BUILT SUCCESSFULLY!")
        print("="*80)
        print()

        # Show stats
        print("Graph Statistics:")
        with neo4j.driver.session() as session:
            # Total nodes
            result = session.run("MATCH (n) RETURN count(n) AS total")
            total = result.single()["total"]
            print(f"  Total nodes: {total}")

            # Total relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS total")
            total_rels = result.single()["total"]
            print(f"  Total relationships: {total_rels}")

            # Nodes by type
            result = session.run("""
                CALL db.labels() YIELD label
                CALL {
                    WITH label
                    MATCH (n)
                    WHERE label IN labels(n)
                    RETURN count(n) AS count
                }
                RETURN label, count
                ORDER BY count DESC
            """)
            print("\n  Nodes by type:")
            for record in result:
                print(f"    {record['label']}: {record['count']}")

            # Top relationships
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS rel_type, count(*) AS count
                ORDER BY count DESC
                LIMIT 10
            """)
            print("\n  Top relationship types:")
            for record in result:
                print(f"    {record['rel_type']}: {record['count']}")

        print("\n" + "="*80)
        print("Next Steps:")
        print("="*80)
        print("1. Restart your API server (if running)")
        print("2. Try a complex medical query")
        print("3. You should now see: [OK] Added knowledge graph context")
        print()

    except Exception as e:
        print("\n" + "="*80)
        print("❌ ERROR BUILDING KNOWLEDGE GRAPH")
        print("="*80)
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you've indexed your PDFs first (run ingestion scripts)")
        print("2. Check that Elasticsearch has documents")
        print("3. Verify Neo4j connection is working")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        neo4j.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
