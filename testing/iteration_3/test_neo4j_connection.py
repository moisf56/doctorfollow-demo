"""
Quick test script to verify Neo4j Aura connection with SSL
Run this to test the fix before restarting the API server
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add to path
sys.path.append(str(Path(__file__).parent))

from neo4j_store import Neo4jStore

def test_connection():
    """Test Neo4j connection"""
    print("="*80)
    print("Testing Neo4j Aura Connection")
    print("="*80)

    # Get credentials from env
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    print(f"\nNeo4j URI: {neo4j_uri}")
    print(f"Neo4j User: {neo4j_user}")
    print(f"Neo4j Password: {'*' * len(neo4j_password) if neo4j_password else 'NOT SET'}")

    if not all([neo4j_uri, neo4j_user, neo4j_password]):
        print("\n[ERROR] Missing Neo4j credentials in .env file")
        return False

    print("\n" + "-"*80)
    print("Attempting connection...")
    print("-"*80 + "\n")

    try:
        # Initialize Neo4j store (tests connection)
        store = Neo4jStore(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )

        # Try a simple query
        print("\nTesting query execution...")
        with store.driver.session() as session:
            result = session.run("RETURN 'Connection successful!' AS message")
            record = result.single()
            message = record["message"]
            print(f"[OK] {message}")

        # Check database info
        print("\nChecking database info...")
        with store.driver.session() as session:
            result = session.run("""
                CALL dbms.components() YIELD name, versions, edition
                RETURN name, versions[0] AS version, edition
            """)
            for record in result:
                print(f"  Database: {record['name']}")
                print(f"  Version: {record['version']}")
                print(f"  Edition: {record['edition']}")

        # Count nodes
        print("\nChecking graph data...")
        with store.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS nodeCount")
            count = result.single()["nodeCount"]
            print(f"  Total nodes: {count}")

            # Count by label
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

        store.close()

        print("\n" + "="*80)
        print("[SUCCESS] Neo4j connection is working!")
        print("="*80)
        return True

    except Exception as e:
        print("\n" + "="*80)
        print("[ERROR] Neo4j connection failed!")
        print("="*80)
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Check that NEO4J_URI starts with 'neo4j+s://' (for Aura)")
        print("2. Verify credentials are correct")
        print("3. Check that your Neo4j Aura instance is running")
        print("4. Ensure your IP is allowed in Neo4j Aura firewall settings")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
