"""
Medical Knowledge Graph Builder - Relationship-Centric Approach
Uses scispaCy NER + relaxed schema + relationship-driven semantics

Modern approach:
- Extract entities with scispaCy medical NER (no hardcoding)
- Use generic "MedicalEntity" type (no forced classification)
- Focus on HIGH-QUALITY relationships
- Let relationships define semantics (TREATS, SYMPTOM_OF, CAUSES, etc.)
"""
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from collections import Counter, defaultdict
import spacy
from math import log

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import OpenSearchStore
from neo4j_store import Neo4jStore


class MedicalKGBuilderFinal:
    """
    Build medical knowledge graph with relationship-centric approach

    Philosophy:
    - Entities are generic "MedicalEntity" nodes
    - Relationships encode the semantics
    - No forced type classification (flexible, fewer errors)
    """

    def __init__(self, opensearch_store: OpenSearchStore, neo4j_store: Neo4jStore):
        """Initialize KG builder with scispaCy"""
        self.opensearch = opensearch_store
        self.neo4j = neo4j_store

        # Load scispaCy medical NLP model
        print("[Loading] scispaCy medical NLP model...")
        try:
            self.nlp = spacy.load("en_core_sci_sm")
            print("[OK] Loaded en_core_sci_sm (biomedical NER)")
        except OSError:
            print("[ERROR] scispaCy model not found")
            raise

    def extract_entities_from_chunks(
        self,
        limit: int = None,
        min_frequency: int = 3,
        top_k_tfidf: int = 200
    ) -> Set[str]:
        """
        Extract medical entities using scispaCy NER

        Returns:
            Set of entity names (no type classification needed)
        """
        print(f"[INFO] Extracting medical entities with scispaCy NER...")

        # Get diverse chunks
        all_chunks = []
        search_terms = [
            "infant", "newborn", "neonatal", "treatment", "disease",
            "respiratory", "cardiac", "therapy", "syndrome", "diagnosis"
        ]
        for term in search_terms:
            results = self.opensearch.search(term, top_k=100)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit] if limit else list(unique_chunks)

        print(f"[OK] Processing {len(chunks)} chunks")

        # Extract entities using scispaCy NER
        entity_counter = Counter()

        print("[INFO] Running medical NER on chunks...")
        for i, chunk in enumerate(chunks):
            if i % 50 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            doc = self.nlp(chunk.text)

            for ent in doc.ents:
                # Normalize entity text
                entity_text = ent.text.lower().strip()

                # Filter out noise
                if len(entity_text) < 3 or entity_text.isdigit():
                    continue
                if entity_text in ["the", "a", "an", "this", "that", "these", "those", "fig", "table"]:
                    continue

                # Filter out pure numbers and dates
                if entity_text.replace(".", "").replace("-", "").isdigit():
                    continue

                entity_counter[entity_text] += 1

        # Filter by frequency
        filtered_entities = {
            entity
            for entity, count in entity_counter.items()
            if count >= min_frequency
        }

        print(f"[OK] Found {len(filtered_entities)} entities (freq >= {min_frequency})")

        # Calculate TF-IDF and select top K
        print("[INFO] Calculating TF-IDF scores...")
        entity_freq = {e: entity_counter[e] for e in filtered_entities}

        df = Counter()
        total_chunks = len(chunks)
        for chunk in chunks:
            text = chunk.text.lower()
            for entity in filtered_entities:
                if entity in text:
                    df[entity] += 1

        tfidf_scores = {}
        for entity in filtered_entities:
            tf = entity_freq[entity]
            if entity in df and df[entity] > 0:
                idf = log(total_chunks / df[entity])
                tfidf_scores[entity] = tf * idf
            else:
                tfidf_scores[entity] = 0.0

        # Select top K by TF-IDF
        sorted_entities = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)
        top_entities = {entity for entity, score in sorted_entities[:top_k_tfidf]}

        print(f"[INFO] Selected top {len(top_entities)} entities by TF-IDF")

        # Show examples
        print(f"\n[SAMPLE ENTITIES]")
        for i, (entity, score) in enumerate(sorted_entities[:10]):
            freq = entity_freq.get(entity, 0)
            print(f"  {i+1}. {entity} (freq: {freq}, tfidf: {score:.2f})")

        return top_entities

    def extract_relationships_from_chunks(
        self,
        chunks: List,
        entities: Set[str]
    ) -> List[Tuple[str, str, str]]:
        """
        Extract relationships with context-based inference

        Relationship types:
        - TREATS: drug/procedure treats disease
        - SYMPTOM_OF: symptom is symptom of disease
        - CAUSES: disease causes symptom/complication
        - ASSOCIATED_WITH: general association
        - USED_FOR: procedure used for condition
        """
        print(f"\n[INFO] Extracting relationships from chunks...")

        relationships = []

        for i, chunk in enumerate(chunks):
            if i % 50 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            text = chunk.text.lower()
            doc = self.nlp(text)

            # Find entities in this chunk
            entities_in_chunk = []
            for entity in entities:
                if entity in text:
                    entities_in_chunk.append(entity)

            # Extract relationships from sentences
            for sent in doc.sents:
                sent_text = sent.text.lower()

                # Find entity pairs in this sentence
                entities_in_sent = [e for e in entities_in_chunk if e in sent_text]

                for i_ent, ent1 in enumerate(entities_in_sent):
                    for ent2 in entities_in_sent[i_ent+1:]:
                        # Infer relationship type from context
                        rel_type = self._infer_relationship(ent1, ent2, sent_text)
                        if rel_type:
                            relationships.append((ent1, ent2, rel_type))

        # Remove duplicates
        relationships = list(set(relationships))

        # Group by type
        rel_by_type = defaultdict(int)
        for _, _, rel_type in relationships:
            rel_by_type[rel_type] += 1

        print(f"[OK] Found {len(relationships)} relationships")
        print(f"\nRelationships by type:")
        for rel_type, count in sorted(rel_by_type.items(), key=lambda x: x[1], reverse=True):
            print(f"  {rel_type}: {count}")

        print(f"\n[SAMPLE RELATIONSHIPS]")
        for rel in relationships[:15]:
            print(f"  ({rel[0]}) -[{rel[2]}]-> ({rel[1]})")

        return relationships

    def _infer_relationship(self, ent1: str, ent2: str, sentence: str) -> str:
        """
        Infer relationship type from sentence context

        Uses keyword patterns to identify relationship semantics
        """
        # TREATS relationship
        if any(kw in sentence for kw in [
            "treat with", "treated with", "therapy for", "given for",
            "administered for", "treatment of", "medication for"
        ]):
            return "TREATS"

        if any(kw in sentence for kw in ["treat", "therapy", "given"]) and \
           any(kw in sentence for kw in ["for", "of"]):
            return "TREATS"

        # SYMPTOM_OF relationship
        if any(kw in sentence for kw in [
            "symptom of", "sign of", "characterized by",
            "presents with", "manifests as", "develops"
        ]):
            return "SYMPTOM_OF"

        # CAUSES relationship
        if any(kw in sentence for kw in [
            "causes", "caused by", "leads to", "results in",
            "due to", "secondary to", "associated with risk"
        ]):
            return "CAUSES"

        # USED_FOR relationship (procedures)
        if any(kw in sentence for kw in [
            "performed for", "used for", "indicated for",
            "procedure for", "intervention for"
        ]):
            return "USED_FOR"

        # ASSOCIATED_WITH (general co-occurrence in medical context)
        if any(kw in sentence for kw in [
            "associated with", "related to", "linked to",
            "found in", "observed in", "seen in"
        ]):
            return "ASSOCIATED_WITH"

        # CO_OCCURS (weaker association, just co-mention)
        # Don't add this - too weak, will create noise

        return None  # No clear relationship

    def build_graph(
        self,
        limit_chunks: int = None,
        min_entity_freq: int = 3,
        top_k_entities: int = 200
    ):
        """
        Build relationship-centric knowledge graph

        Args:
            limit_chunks: Limit number of chunks to process
            min_entity_freq: Minimum frequency for entity inclusion
            top_k_entities: Top K entities by TF-IDF
        """
        print("="*80)
        print("BUILDING MEDICAL KNOWLEDGE GRAPH")
        print("Approach: Relationship-Centric + scispaCy NER")
        print("="*80)
        print()

        # Step 1: Extract entities
        entities = self.extract_entities_from_chunks(
            limit=limit_chunks,
            min_frequency=min_entity_freq,
            top_k_tfidf=top_k_entities
        )

        # Step 2: Add entities to Neo4j as generic MedicalEntity nodes
        print(f"\n[INFO] Adding entities to Neo4j...")

        # Create generic MedicalEntity nodes
        with self.neo4j.driver.session() as session:
            for entity in entities:
                query = """
                MERGE (e:MedicalEntity {name: $name})
                ON CREATE SET e.source = 'scispaCy NER'
                """
                session.run(query, name=entity)

        print(f"[OK] Added {len(entities)} MedicalEntity nodes to graph")

        # Step 3: Extract relationships
        all_chunks = []
        for term in ["infant", "newborn", "treatment", "respiratory", "disease", "therapy"]:
            results = self.opensearch.search(term, top_k=100)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit_chunks] if limit_chunks else list(unique_chunks)

        relationships = self.extract_relationships_from_chunks(chunks, entities)

        # Step 4: Add relationships to Neo4j
        print(f"\n[INFO] Adding relationships to Neo4j...")
        rel_count = 0

        with self.neo4j.driver.session() as session:
            for source, target, rel_type in relationships:
                # Use MERGE to avoid duplicates
                query = f"""
                MATCH (a:MedicalEntity {{name: $source}})
                MATCH (b:MedicalEntity {{name: $target}})
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r.source = 'scispaCy NER + context'
                """
                try:
                    session.run(query, source=source, target=target)
                    rel_count += 1
                except Exception as e:
                    pass  # Skip if error

        print(f"[OK] Added {rel_count} relationships to graph")

        # Step 5: Show stats
        print("\n" + "="*80)
        print("KNOWLEDGE GRAPH BUILT")
        print("="*80)

        with self.neo4j.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n:MedicalEntity) RETURN count(n) as count")
            node_count = result.single()["count"]

            # Count relationships by type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """)

            print(f"\nTotal MedicalEntity nodes: {node_count}")
            print(f"Total relationships: {rel_count}")
            print(f"\nRelationships by type:")
            for record in result:
                print(f"  {record['rel_type']}: {record['count']}")


if __name__ == "__main__":
    print("=== Medical Knowledge Graph Builder (Final - Relationship-Centric) ===\n")

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

    # Build relationship-centric KG
    builder = MedicalKGBuilderFinal(opensearch, neo4j)
    builder.build_graph(
        limit_chunks=500,
        min_entity_freq=3,
        top_k_entities=200
    )

    # Cleanup
    opensearch.close()
    neo4j.close()

    print("\n[OK] Relationship-centric knowledge graph build complete!")
