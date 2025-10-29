"""
Inspect the actual graph structure from LLM Graph Builder
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from neo4j_store import Neo4jStore
from config import settings


print("="*80)
print("GRAPH STRUCTURE INSPECTION")
print("="*80)

neo4j = Neo4jStore(
    uri=settings.NEO4J_URI,
    user=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD
)

with neo4j.driver.session() as session:
    # 1. Check if entities have an 'id' property (typical for LLM Graph Builder)
    print("\n[1] Checking __Entity__ properties...")
    result = session.run("""
        MATCH (e:__Entity__)
        RETURN e.id AS id, labels(e) AS labels
        LIMIT 3
    """)
    print("Sample entities:")
    for record in result:
        print(f"  ID: {record['id']}, Labels: {record['labels']}")

    # 2. Check if there are additional labels beyond __Entity__
    print("\n[2] Checking all labels (entity types)...")
    result = session.run("""
        CALL db.labels() YIELD label
        RETURN label
        ORDER BY label
    """)
    all_labels = [record["label"] for record in result]
    print(f"Total labels: {len(all_labels)}")
    print("Labels:", ", ".join(all_labels[:20]))
    if len(all_labels) > 20:
        print(f"... and {len(all_labels) - 20} more")

    # 3. Check relationship types
    print("\n[3] Checking relationship types...")
    result = session.run("""
        CALL db.relationshipTypes() YIELD relationshipType
        RETURN relationshipType
        ORDER BY relationshipType
        LIMIT 20
    """)
    print("Relationship types:")
    for record in result:
        print(f"  - {record['relationshipType']}")

    # 4. Sample relationships
    print("\n[4] Sample relationships...")
    result = session.run("""
        MATCH (e1:__Entity__)-[r]->(e2:__Entity__)
        RETURN e1.id AS source, type(r) AS rel_type, e2.id AS target
        LIMIT 10
    """)
    print("Sample entity relationships:")
    for record in result:
        print(f"  {record['source']} --[{record['rel_type']}]--> {record['target']}")

    # 5. Check for SIMILAR relationships (semantic links)
    print("\n[5] Checking SIMILAR relationships...")
    result = session.run("""
        MATCH ()-[r:SIMILAR]->()
        RETURN count(r) AS count
    """).single()
    similar_count = result["count"]
    print(f"Total SIMILAR relationships: {similar_count}")

    if similar_count > 0:
        result = session.run("""
            MATCH (c1:Chunk)-[r:SIMILAR]->(c2:Chunk)
            RETURN c1.id AS chunk1, c2.id AS chunk2
            LIMIT 3
        """)
        print("Sample SIMILAR relationships:")
        for record in result:
            print(f"  {record['chunk1']} --[SIMILAR]--> {record['chunk2']}")

    # 6. Check how entities are organized
    print("\n[6] Checking entity organization...")
    result = session.run("""
        MATCH (e:__Entity__)
        WHERE e.id IS NOT NULL
        RETURN e.id AS entity_id
        LIMIT 5
    """)
    print("Sample entity IDs:")
    for record in result:
        print(f"  - {record['entity_id']}")

neo4j.close()
print("\n[COMPLETE]")
