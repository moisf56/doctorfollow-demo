"""
Neo4j Knowledge Graph Store for DoctorFollow Medical Search Agent
Iteration 3: Medical knowledge graph for relationship-based retrieval

Entities from our neonatal medicine PDF:
- Diseases: PPHN, PDA, hyperthyroidism, apnea, meconium aspiration, RDS
- Procedures: cardiac massage, intubation, ventilation, ECMO
- Drugs: acyclovir, penicillin, ampicillin
- Symptoms: respiratory distress, bradycardia, hypoxia, apnea
- Anatomy: ductus arteriosus, foramen ovale, pulmonary artery
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from dataclasses import dataclass


@dataclass
class Entity:
    """Medical entity in the knowledge graph"""
    name: str
    type: str  # disease, drug, procedure, symptom, anatomy
    properties: Dict[str, Any]


@dataclass
class Relationship:
    """Relationship between entities"""
    source: str
    target: str
    rel_type: str  # TREATS, CAUSES, HAS_SYMPTOM, USED_FOR, etc.
    properties: Dict[str, Any]


class Neo4jStore:
    """
    Neo4j client for medical knowledge graph

    Schema:
    - Nodes: Disease, Drug, Procedure, Symptom, Anatomy
    - Relationships: TREATS, CAUSES, HAS_SYMPTOM, USED_FOR, PART_OF, etc.
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j URI (e.g., bolt://localhost:7687)
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print(f"[OK] Connected to Neo4j at {uri}")

        # Create constraints and indexes
        self._create_schema()

    def _create_schema(self):
        """Create schema constraints and indexes"""
        with self.driver.session() as session:
            # Unique constraints on entity names
            constraints = [
                "CREATE CONSTRAINT disease_name IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
                "CREATE CONSTRAINT drug_name IF NOT EXISTS FOR (d:Drug) REQUIRE d.name IS UNIQUE",
                "CREATE CONSTRAINT procedure_name IF NOT EXISTS FOR (p:Procedure) REQUIRE p.name IS UNIQUE",
                "CREATE CONSTRAINT symptom_name IF NOT EXISTS FOR (s:Symptom) REQUIRE s.name IS UNIQUE",
                "CREATE CONSTRAINT anatomy_name IF NOT EXISTS FOR (a:Anatomy) REQUIRE a.name IS UNIQUE",
            ]

            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception:
                    pass  # Constraint already exists

            print("[OK] Neo4j schema initialized")

    def add_entity(self, entity: Entity) -> bool:
        """
        Add or update an entity in the graph

        Args:
            entity: Entity to add

        Returns:
            True if successful
        """
        with self.driver.session() as session:
            query = f"""
            MERGE (e:{entity.type.capitalize()} {{name: $name}})
            SET e += $properties
            RETURN e
            """

            result = session.run(
                query,
                name=entity.name,
                properties=entity.properties
            )

            return result.single() is not None

    def add_relationship(self, relationship: Relationship) -> bool:
        """
        Add a relationship between entities

        Args:
            relationship: Relationship to add

        Returns:
            True if successful
        """
        with self.driver.session() as session:
            # Find source and target nodes (any type)
            query = f"""
            MATCH (s) WHERE s.name = $source
            MATCH (t) WHERE t.name = $target
            MERGE (s)-[r:{relationship.rel_type}]->(t)
            SET r += $properties
            RETURN r
            """

            result = session.run(
                query,
                source=relationship.source,
                target=relationship.target,
                properties=relationship.properties
            )

            return result.single() is not None

    def find_related_entities(
        self,
        entity_name: str,
        max_hops: int = 2,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find entities related to a given entity (multi-hop traversal)

        Args:
            entity_name: Name of the entity to start from
            max_hops: Maximum number of hops (default 2)
            limit: Maximum results to return

        Returns:
            List of related entities with paths
        """
        with self.driver.session() as session:
            query = f"""
            MATCH path = (start)-[*1..{max_hops}]-(related)
            WHERE start.name = $entity_name
            AND start <> related
            RETURN DISTINCT
                related.name AS name,
                labels(related)[0] AS type,
                [r IN relationships(path) | type(r)] AS path_types,
                length(path) AS distance
            ORDER BY distance, name
            LIMIT $limit
            """

            result = session.run(
                query,
                entity_name=entity_name,
                limit=limit
            )

            entities = []
            for record in result:
                entities.append({
                    "name": record["name"],
                    "type": record["type"],
                    "path": record["path_types"],
                    "distance": record["distance"]
                })

            return entities

    def find_treatment_for(self, disease_name: str) -> List[Dict[str, Any]]:
        """
        Find treatments (drugs/procedures) for a disease

        Args:
            disease_name: Name of the disease

        Returns:
            List of treatments
        """
        with self.driver.session() as session:
            query = """
            MATCH (d:Disease {name: $disease_name})<-[:TREATS]-(treatment)
            RETURN treatment.name AS name, labels(treatment)[0] AS type
            """

            result = session.run(query, disease_name=disease_name)

            return [{"name": r["name"], "type": r["type"]} for r in result]

    def find_symptoms_of(self, disease_name: str) -> List[str]:
        """
        Find symptoms of a disease

        Args:
            disease_name: Name of the disease

        Returns:
            List of symptom names
        """
        with self.driver.session() as session:
            query = """
            MATCH (d:Disease {name: $disease_name})-[:HAS_SYMPTOM]->(s:Symptom)
            RETURN s.name AS symptom
            """

            result = session.run(query, disease_name=disease_name)

            return [r["symptom"] for r in result]

    def get_entity_context(self, entity_name: str) -> str:
        """
        Get rich context about an entity from the graph

        Args:
            entity_name: Name of the entity

        Returns:
            Text description of the entity and its relationships
        """
        with self.driver.session() as session:
            # Get entity type and properties
            query_entity = """
            MATCH (e {name: $entity_name})
            RETURN labels(e)[0] AS type, properties(e) AS props
            """

            entity_result = session.run(query_entity, entity_name=entity_name).single()

            if not entity_result:
                return f"No information found for: {entity_name}"

            entity_type = entity_result["type"]
            context_parts = [f"{entity_name} ({entity_type})"]

            # Get relationships
            query_rels = """
            MATCH (e {name: $entity_name})-[r]-(other)
            RETURN type(r) AS rel_type,
                   other.name AS other_name,
                   labels(other)[0] AS other_type,
                   startNode(r).name = $entity_name AS outgoing
            LIMIT 20
            """

            rels_result = session.run(query_rels, entity_name=entity_name)

            # Group by relationship type
            rel_groups = {}
            for record in rels_result:
                rel_type = record["rel_type"]
                other_name = record["other_name"]
                is_outgoing = record["outgoing"]

                if rel_type not in rel_groups:
                    rel_groups[rel_type] = {"outgoing": [], "incoming": []}

                if is_outgoing:
                    rel_groups[rel_type]["outgoing"].append(other_name)
                else:
                    rel_groups[rel_type]["incoming"].append(other_name)

            # Build context text
            for rel_type, directions in rel_groups.items():
                if directions["outgoing"]:
                    context_parts.append(
                        f"- {rel_type}: {', '.join(directions['outgoing'])}"
                    )
                if directions["incoming"]:
                    context_parts.append(
                        f"- {rel_type} (incoming): {', '.join(directions['incoming'])}"
                    )

            return "\n".join(context_parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        with self.driver.session() as session:
            # Count nodes by type
            node_counts = {}
            for label in ["Disease", "Drug", "Procedure", "Symptom", "Anatomy"]:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
                node_counts[label] = result.single()["count"]

            # Count relationships
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) AS count")
            rel_count = rel_result.single()["count"]

            return {
                "nodes": node_counts,
                "total_nodes": sum(node_counts.values()),
                "total_relationships": rel_count
            }

    def clear_graph(self):
        """Delete all nodes and relationships (use with caution!)"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("[OK] Graph cleared")

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()


if __name__ == "__main__":
    # Test Neo4j connection and basic operations
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config import settings

    print("=== Neo4j Store Test ===\n")

    # Connect
    store = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    # Add test entities from our PDF content
    print("\n[TEST] Adding entities from neonatal medicine PDF...")

    entities = [
        Entity("PPHN", "disease", {"full_name": "Persistent Pulmonary Hypertension"}),
        Entity("PDA", "disease", {"full_name": "Patent Ductus Arteriosus"}),
        Entity("apnea", "symptom", {"description": "Cessation of breathing"}),
        Entity("respiratory_distress", "symptom", {"description": "Difficulty breathing"}),
        Entity("cardiac_massage", "procedure", {"description": "External cardiac compression"}),
        Entity("acyclovir", "drug", {"description": "Antiviral medication"}),
    ]

    for entity in entities:
        store.add_entity(entity)
        print(f"  Added: {entity.name} ({entity.type})")

    # Add relationships
    print("\n[TEST] Adding relationships...")

    relationships = [
        Relationship("PPHN", "respiratory_distress", "HAS_SYMPTOM", {}),
        Relationship("cardiac_massage", "bradycardia", "USED_FOR", {}),
        Relationship("acyclovir", "neonatal_HSV", "TREATS", {}),
        Relationship("PDA", "respiratory_distress", "CAUSES", {}),
    ]

    for rel in relationships:
        # Add missing entities first
        if rel.target not in [e.name for e in entities]:
            store.add_entity(Entity(rel.target, "disease", {}))

        store.add_relationship(rel)
        print(f"  Added: {rel.source} -[{rel.rel_type}]-> {rel.target}")

    # Test queries
    print("\n[TEST] Finding related entities to PPHN...")
    related = store.find_related_entities("PPHN", max_hops=2)
    for r in related:
        print(f"  {r['name']} ({r['type']}) - distance: {r['distance']}")

    # Get context
    print("\n[TEST] Getting context for PPHN...")
    context = store.get_entity_context("PPHN")
    print(context)

    # Stats
    print("\n[TEST] Graph statistics:")
    stats = store.get_stats()
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total relationships: {stats['total_relationships']}")
    for label, count in stats['nodes'].items():
        if count > 0:
            print(f"  {label}: {count}")

    store.close()
    print("\n[OK] Test complete!")
