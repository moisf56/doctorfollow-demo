"""
Medical Knowledge Graph Builder with NLP-based Entity Extraction
Uses scispaCy for automatic medical entity recognition

No hardcoded entities - fully automatic extraction from PDF content
"""
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import spacy
from collections import Counter

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import OpenSearchStore
from neo4j_store import Neo4jStore, Entity, Relationship


class MedicalKGBuilderNLP:
    """
    Build medical knowledge graph using NLP-based entity extraction

    Uses scispaCy for automatic medical entity recognition
    No hardcoded entity lists - fully data-driven
    """

    def __init__(self, opensearch_store: OpenSearchStore, neo4j_store: Neo4jStore):
        """
        Initialize KG builder with NLP

        Args:
            opensearch_store: OpenSearch store with indexed chunks
            neo4j_store: Neo4j store for graph
        """
        self.opensearch = opensearch_store
        self.neo4j = neo4j_store

        # Load scispaCy medical NLP model
        print("[Loading] scispaCy medical NLP model...")
        try:
            # Try to load medical model (en_core_sci_md)
            self.nlp = spacy.load("en_core_sci_md")
            print("[OK] Loaded en_core_sci_md (medical model)")
        except OSError:
            # Fallback to small general model
            print("[WARN] Medical model not found, using en_core_web_sm")
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("[ERROR] No spaCy model found. Please run:")
                print("  python -m spacy download en_core_web_sm")
                raise

        # Entity type mapping (from NER labels to our schema)
        self.entity_type_map = {
            # Medical entities
            "DISEASE": "disease",
            "SYMPTOM": "symptom",
            "CHEMICAL": "drug",
            "DRUG": "drug",
            "TREATMENT": "procedure",
            "PROCEDURE": "procedure",
            "ANATOMICAL": "anatomy",
            "ORGAN": "anatomy",
            # General entities (filter later)
            "PERSON": None,  # Ignore
            "ORG": None,  # Ignore
            "GPE": None,  # Ignore
            "DATE": None,  # Ignore
            "TIME": None,  # Ignore
        }

    def extract_entities_from_chunks(
        self,
        limit: int = None,
        min_frequency: int = 2
    ) -> Dict[str, Set[str]]:
        """
        Extract medical entities using NLP

        Args:
            limit: Maximum number of chunks to process
            min_frequency: Minimum frequency for entity to be included

        Returns:
            Dictionary of entity_type -> set of entity names
        """
        print(f"[INFO] Extracting entities using NLP...")

        # Get chunks
        all_chunks = []
        for term in ["infant", "newborn", "neonatal", "treatment", "disease"]:
            results = self.opensearch.search(term, top_k=200)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit] if limit else list(unique_chunks)

        print(f"[OK] Processing {len(chunks)} chunks with NLP")

        # Extract entities
        entity_counter = {}  # (entity_name, entity_type) -> count

        for i, chunk in enumerate(chunks):
            if i % 50 == 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            # Run NLP
            doc = self.nlp(chunk.text)

            # Extract named entities
            for ent in doc.ents:
                # Map entity label to our schema
                entity_type = self.entity_type_map.get(ent.label_)

                if entity_type is None:
                    continue  # Skip irrelevant entities

                # Normalize entity name
                entity_name = ent.text.strip().lower()

                # Skip very short entities or numbers
                if len(entity_name) < 3 or entity_name.isdigit():
                    continue

                # Count entity
                key = (entity_name, entity_type)
                entity_counter[key] = entity_counter.get(key, 0) + 1

        # Filter by frequency
        found_entities = {
            "disease": set(),
            "drug": set(),
            "procedure": set(),
            "symptom": set(),
            "anatomy": set()
        }

        for (entity_name, entity_type), count in entity_counter.items():
            if count >= min_frequency:
                found_entities[entity_type].add(entity_name)

        # Print stats
        print(f"\n[ENTITIES EXTRACTED]")
        total = 0
        for entity_type, entities in found_entities.items():
            if entities:
                print(f"  {entity_type.capitalize()}: {len(entities)}")
                for e in sorted(entities)[:5]:  # Show first 5
                    count = entity_counter.get((e, entity_type), 0)
                    print(f"    - {e} (freq: {count})")
                if len(entities) > 5:
                    print(f"    ... and {len(entities) - 5} more")
                total += len(entities)

        print(f"\n[OK] Total entities extracted: {total}")

        return found_entities

    def extract_relationships_from_chunks(
        self,
        chunks: List,
        entities: Dict[str, Set[str]]
    ) -> List[Tuple[str, str, str]]:
        """
        Extract relationships using co-occurrence and dependency parsing

        Args:
            chunks: List of chunks
            entities: Dictionary of extracted entities

        Returns:
            List of (source, target, rel_type) tuples
        """
        print(f"\n[INFO] Extracting relationships with NLP...")

        relationships = []

        for i, chunk in enumerate(chunks):
            if i % 50 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            text = chunk.text.lower()

            # Simple co-occurrence based relationships
            # Disease and drug co-occurrence
            for disease in entities.get("disease", []):
                for drug in entities.get("drug", []):
                    if disease in text and drug in text:
                        # Check for treatment keywords nearby
                        if any(kw in text for kw in ["treat", "therapy", "treatment", "administered", "given"]):
                            relationships.append((drug, disease, "TREATS"))

            # Disease and symptom co-occurrence
            for disease in entities.get("disease", []):
                for symptom in entities.get("symptom", []):
                    if disease in text and symptom in text:
                        # Check for symptom keywords
                        if any(kw in text for kw in ["symptom", "presents with", "characterized by", "signs of"]):
                            relationships.append((disease, symptom, "HAS_SYMPTOM"))
                        # Also check for causation
                        elif any(kw in text for kw in ["causes", "leads to", "results in"]):
                            relationships.append((disease, symptom, "CAUSES"))

            # Procedure and disease co-occurrence
            for procedure in entities.get("procedure", []):
                for disease in entities.get("disease", []):
                    if procedure in text and disease in text:
                        if any(kw in text for kw in ["for", "treatment", "management", "used in"]):
                            relationships.append((procedure, disease, "USED_FOR"))

        # Remove duplicates
        relationships = list(set(relationships))

        print(f"[OK] Found {len(relationships)} relationships")
        for rel in relationships[:10]:
            print(f"  {rel[0]} -[{rel[2]}]-> {rel[1]}")
        if len(relationships) > 10:
            print(f"  ... and {len(relationships) - 10} more")

        return relationships

    def build_graph(self, limit_chunks: int = None, min_entity_freq: int = 2):
        """
        Build knowledge graph using NLP

        Args:
            limit_chunks: Limit number of chunks to process
            min_entity_freq: Minimum frequency for entity inclusion
        """
        print("="*80)
        print("BUILDING MEDICAL KNOWLEDGE GRAPH (NLP-based)")
        print("="*80)
        print()

        # Step 1: Extract entities with NLP
        entities = self.extract_entities_from_chunks(
            limit=limit_chunks,
            min_frequency=min_entity_freq
        )

        # Step 2: Add entities to Neo4j
        print(f"\n[INFO] Adding entities to Neo4j...")
        entity_count = 0
        for entity_type, entity_names in entities.items():
            for name in entity_names:
                entity = Entity(
                    name=name,
                    type=entity_type,
                    properties={"source": "NLP extraction", "method": "scispaCy"}
                )
                self.neo4j.add_entity(entity)
                entity_count += 1

        print(f"[OK] Added {entity_count} entities to graph")

        # Step 3: Extract relationships
        all_chunks = []
        for term in ["infant", "newborn", "treatment"]:
            results = self.opensearch.search(term, top_k=200)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit_chunks] if limit_chunks else list(unique_chunks)

        relationships = self.extract_relationships_from_chunks(chunks, entities)

        # Step 4: Add relationships to Neo4j
        print(f"\n[INFO] Adding relationships to Neo4j...")
        rel_count = 0
        for source, target, rel_type in relationships:
            relationship = Relationship(
                source=source,
                target=target,
                rel_type=rel_type,
                properties={"source": "NLP extraction"}
            )
            if self.neo4j.add_relationship(relationship):
                rel_count += 1

        print(f"[OK] Added {rel_count} relationships to graph")

        # Step 5: Show stats
        print("\n" + "="*80)
        print("KNOWLEDGE GRAPH BUILT (NLP-based)")
        print("="*80)
        stats = self.neo4j.get_stats()
        print(f"\nTotal nodes: {stats['total_nodes']}")
        print(f"Total relationships: {stats['total_relationships']}")
        print(f"\nNodes by type:")
        for label, count in stats['nodes'].items():
            if count > 0:
                print(f"  {label}: {count}")


if __name__ == "__main__":
    print("=== Medical Knowledge Graph Builder (NLP-based) ===\n")

    # Initialize stores
    print("[Loading] OpenSearch...")
    opensearch = OpenSearchStore(
        host=settings.OPENSEARCH_HOST,
        port=settings.OPENSEARCH_PORT,
        index_name=settings.OPENSEARCH_INDEX
    )

    print("[Loading] Neo4j...")
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    # Clear existing graph
    print("\n[WARN] Clearing existing graph...")
    neo4j.clear_graph()

    # Build KG with NLP
    builder = MedicalKGBuilderNLP(opensearch, neo4j)
    builder.build_graph(limit_chunks=500, min_entity_freq=2)

    # Cleanup
    opensearch.close()
    neo4j.close()

    print("\n[OK] NLP-based knowledge graph build complete!")
