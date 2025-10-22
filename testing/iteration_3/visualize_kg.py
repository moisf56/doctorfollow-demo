"""
Export Knowledge Graph for visualization
Creates JSON data that can be visualized with D3.js, Cytoscape, etc.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os
import json

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add to path
sys.path.append(str(Path(__file__).parent))

from neo4j_store import Neo4jStore

def export_graph_to_json(neo4j_store: Neo4jStore, output_file: str = "kg_visualization.json", max_nodes: int = 200):
    """Export graph data to JSON for visualization"""

    print(f"Exporting Knowledge Graph to {output_file}...")

    with neo4j_store.driver.session() as session:
        # Get nodes
        print("  Fetching nodes...")
        result = session.run(f"""
            MATCH (n)
            RETURN id(n) AS id, labels(n) AS labels, n.name AS name
            LIMIT {max_nodes}
        """)

        nodes = []
        node_ids = set()
        for record in result:
            node_id = record["id"]
            node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "label": record["name"],
                "type": record["labels"][0] if record["labels"] else "Unknown",
                "group": record["labels"][0] if record["labels"] else "Unknown"
            })

        print(f"    Found {len(nodes)} nodes")

        # Get relationships between those nodes
        print("  Fetching relationships...")
        result = session.run(f"""
            MATCH (n)-[r]->(m)
            WHERE id(n) IN $node_ids AND id(m) IN $node_ids
            RETURN id(n) AS source, id(m) AS target, type(r) AS type
        """, node_ids=list(node_ids))

        links = []
        for record in result:
            links.append({
                "source": record["source"],
                "target": record["target"],
                "type": record["type"],
                "label": record["type"]
            })

        print(f"    Found {len(links)} relationships")

    # Create graph data
    graph_data = {
        "nodes": nodes,
        "links": links,
        "metadata": {
            "total_nodes": len(nodes),
            "total_links": len(links),
            "note": f"Limited to {max_nodes} nodes for visualization"
        }
    }

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Exported to {output_file}")
    print(f"\nGraph Statistics:")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Links: {len(links)}")

    # Count by type
    type_counts = {}
    for node in nodes:
        node_type = node["type"]
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    print(f"\n  Nodes by type:")
    for node_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {node_type}: {count}")

    return output_file

def print_interesting_patterns(neo4j_store: Neo4jStore):
    """Print some interesting patterns from the graph"""

    print("\n" + "="*80)
    print("INTERESTING KNOWLEDGE PATTERNS")
    print("="*80)

    with neo4j_store.driver.session() as session:
        # Most connected diseases
        print("\n1. Most Connected Diseases (most relationships):")
        result = session.run("""
            MATCH (d:Disease)-[r]-()
            RETURN d.name AS disease, count(r) AS connections
            ORDER BY connections DESC
            LIMIT 10
        """)
        for i, record in enumerate(result, 1):
            print(f"   {i}. {record['disease']}: {record['connections']} connections")

        # Diseases with most treatments
        print("\n2. Diseases with Most Treatment Options:")
        result = session.run("""
            MATCH (d:Disease)<-[:TREATS]-(treatment)
            RETURN d.name AS disease, count(treatment) AS treatments
            ORDER BY treatments DESC
            LIMIT 10
        """)
        for i, record in enumerate(result, 1):
            print(f"   {i}. {record['disease']}: {record['treatments']} treatments")

        # Most versatile drugs (treats most diseases)
        print("\n3. Most Versatile Drugs (treats most diseases):")
        result = session.run("""
            MATCH (drug:Drug)-[:TREATS]->(d:Disease)
            RETURN drug.name AS drug, count(d) AS diseases
            ORDER BY diseases DESC
            LIMIT 10
        """)
        for i, record in enumerate(result, 1):
            print(f"   {i}. {record['drug']}: treats {record['diseases']} diseases")

        # Example: RDS treatment pathway
        print("\n4. Example: RDS (Respiratory Distress Syndrome) Knowledge:")
        result = session.run("""
            MATCH (rds {name: 'RDS'})-[r]-(related)
            RETURN type(r) AS relationship, labels(related)[0] AS type, related.name AS entity
            LIMIT 20
        """)
        print("   Relationships:")
        for record in result:
            print(f"     {record['entity']} ({record['type']}) - {record['relationship']}")

def main():
    print("="*80)
    print("KNOWLEDGE GRAPH VISUALIZATION EXPORT")
    print("="*80)
    print()

    # Get credentials
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    # Connect to Neo4j
    print("Connecting to Neo4j...")
    neo4j = Neo4jStore(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )
    print()

    # Export graph
    output_file = export_graph_to_json(neo4j, max_nodes=200)

    # Show interesting patterns
    print_interesting_patterns(neo4j)

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"\n1. JSON file created: {output_file}")
    print("   - Can be used with D3.js, Cytoscape.js, or other graph viz tools")
    print()
    print("2. For interactive visualization:")
    print("   a) Neo4j Browser: https://console.neo4j.io")
    print("      - Open your database")
    print("      - Run: MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50")
    print()
    print("   b) Neo4j Bloom (visual exploration):")
    print("      - Click 'Explore' in Neo4j Aura Console")
    print("      - Search for entities like 'PPHN', 'RDS', etc.")
    print()

    neo4j.close()

if __name__ == "__main__":
    main()
