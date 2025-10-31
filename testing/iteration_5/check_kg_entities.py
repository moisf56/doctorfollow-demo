"""
Quick script to check if entities exist in Neo4j graph
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_3"))

from config import settings
from neo4j_store import Neo4jStore

# Connect to Neo4j
neo4j = Neo4jStore(
    uri=settings.NEO4J_URI,
    user=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD
)

# Check for GBS-related entities
print("="*60)
print("Searching for GBS (Group B Streptococcus) entities...")
print("="*60)

with neo4j.driver.session() as session:
    # Search for GBS variations
    queries = [
        "GBS",
        "Group B Streptococcus",
        "Streptococcus",
        "streptococcus",
        "sepsis",
        "neonatal",
        "WBC",
        "CRP"
    ]

    for search_term in queries:
        query = """
        MATCH (e)
        WHERE toLower(e.name) CONTAINS toLower($search_term)
        AND e.name IS NOT NULL
        AND NOT e:Chunk
        AND NOT e:Document
        RETURN e.name AS name, labels(e) AS labels
        LIMIT 5
        """
        result = session.run(query, search_term=search_term)
        entities = list(result)

        if entities:
            print(f"\n✅ Found entities matching '{search_term}':")
            for record in entities:
                print(f"  - {record['name']} ({record['labels']})")
        else:
            print(f"\n❌ No entities found matching '{search_term}'")

    # Check total entity count
    print("\n" + "="*60)
    print("Graph Statistics:")
    print("="*60)

    stats_query = """
    MATCH (e:__Entity__)
    RETURN count(e) as entity_count
    """
    result = session.run(stats_query).single()
    print(f"Total entities: {result['entity_count']}")

    # Check relationships
    rel_query = """
    MATCH ()-[r]->()
    WHERE NOT type(r) IN ['PART_OF', 'NEXT_CHUNK', 'HAS_ENTITY']
    RETURN type(r) as rel_type, count(*) as count
    ORDER BY count DESC
    LIMIT 10
    """
    result = session.run(rel_query)
    print(f"\nTop 10 relationship types:")
    for record in result:
        print(f"  - {record['rel_type']}: {record['count']}")

neo4j.close()
print("\n✅ Done!")
