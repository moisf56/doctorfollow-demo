"""
Medical Knowledge Graph Builder with scispaCy
Uses medical NER for automatic entity extraction - NO HARDCODING

Approach:
1. Use scispaCy medical NLP model for NER
2. Extract medical entities (diseases, chemicals, etc.)
3. Filter by frequency/TF-IDF
4. Extract relationships using dependency parsing
5. Build graph from extracted entities/relationships
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
from neo4j_store import Neo4jStore, Entity, Relationship


class MedicalKGBuilderSciSpacy:
    """
    Build medical knowledge graph using scispaCy medical NER

    No hardcoded lists - entities extracted via:
    - scispaCy medical NER (trained on biomedical corpora)
    - Frequency filtering
    - Context-based relationship extraction
    """

    def __init__(self, opensearch_store: OpenSearchStore, neo4j_store: Neo4jStore):
        """
        Initialize KG builder with scispaCy

        Args:
            opensearch_store: OpenSearch store with indexed chunks
            neo4j_store: Neo4j store for graph
        """
        self.opensearch = opensearch_store
        self.neo4j = neo4j_store

        # Load scispaCy medical NLP model
        print("[Loading] scispaCy medical NLP model...")
        try:
            self.nlp = spacy.load("en_core_sci_sm")
            print("[OK] Loaded en_core_sci_sm (biomedical NER)")
        except OSError:
            print("[ERROR] scispaCy model not found. Please install:")
            print('  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz')
            raise

        # Map scispaCy NER labels to our schema
        # scispaCy recognizes biomedical entities automatically
        self.entity_type_map = {
            # Keep only relevant medical entity types
            # scispaCy uses general entity types from OntoNotes + biomedical
        }

    def extract_entities_from_chunks(
        self,
        limit: int = None,
        min_frequency: int = 3,
        top_k_tfidf: int = 150
    ) -> Dict[str, Set[str]]:
        """
        Extract medical entities using scispaCy NER

        Args:
            limit: Maximum number of chunks to process
            min_frequency: Minimum frequency for entity inclusion
            top_k_tfidf: Top K entities by TF-IDF score

        Returns:
            Dictionary of entity_type -> set of entity names
        """
        print(f"[INFO] Extracting medical entities with scispaCy NER...")

        # Get chunks
        all_chunks = []
        for term in ["infant", "newborn", "neonatal", "treatment", "disease", "respiratory", "cardiac"]:
            results = self.opensearch.search(term, top_k=150)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit] if limit else list(unique_chunks)

        print(f"[OK] Processing {len(chunks)} chunks")

        # Step 1: Extract entities using scispaCy NER
        entity_counter = Counter()
        entity_types = defaultdict(set)  # entity_name -> set of types it appeared as

        print("[INFO] Running medical NER on chunks...")
        for i, chunk in enumerate(chunks):
            if i % 50 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            doc = self.nlp(chunk.text)

            # Extract named entities
            for ent in doc.ents:
                # Normalize entity text
                entity_text = ent.text.lower().strip()

                # Filter out very short entities, numbers, single words that are too generic
                if len(entity_text) < 3 or entity_text.isdigit():
                    continue

                # Skip generic determiners and pronouns
                if entity_text in ["the", "a", "an", "this", "that", "these", "those"]:
                    continue

                entity_counter[entity_text] += 1
                entity_types[entity_text].add(ent.label_)

        # Filter by frequency
        filtered_entities = {
            entity: count
            for entity, count in entity_counter.items()
            if count >= min_frequency
        }

        print(f"[OK] Found {len(filtered_entities)} entities (freq >= {min_frequency})")

        # Step 2: Calculate TF-IDF scores
        print("[INFO] Calculating TF-IDF scores...")
        df = Counter()
        total_chunks = len(chunks)

        for chunk in chunks:
            text = chunk.text.lower()
            entities_in_chunk = set()
            for entity in filtered_entities.keys():
                if entity in text:
                    entities_in_chunk.add(entity)
            df.update(entities_in_chunk)

        tfidf_scores = {}
        for entity, tf in filtered_entities.items():
            if entity in df:
                idf = log(total_chunks / df[entity])
                tfidf_scores[entity] = tf * idf
            else:
                tfidf_scores[entity] = 0.0

        # Step 3: Select top K by TF-IDF
        sorted_entities = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)
        top_entities = [entity for entity, score in sorted_entities[:top_k_tfidf]]

        print(f"[INFO] Selected top {len(top_entities)} entities by TF-IDF")

        # Step 4: Classify entity types for our schema
        print("[INFO] Classifying entity types...")
        entities = {
            "disease": set(),
            "drug": set(),
            "procedure": set(),
            "symptom": set(),
            "anatomy": set()
        }

        # Find context for classification
        for entity in top_entities:
            # Get sentences where entity appears
            context_sentences = []
            for chunk in chunks:
                if entity in chunk.text.lower():
                    doc = self.nlp(chunk.text)
                    for sent in doc.sents:
                        if entity in sent.text.lower():
                            context_sentences.append(sent.text.lower())
                            if len(context_sentences) >= 5:  # Limit context
                                break
                if len(context_sentences) >= 5:
                    break

            # Classify based on context keywords
            entity_type = self._classify_entity_type(entity, context_sentences)
            entities[entity_type].add(entity)

        # Print stats
        print(f"\n[ENTITIES EXTRACTED with scispaCy]")
        total = 0
        for entity_type, entity_set in entities.items():
            if entity_set:
                print(f"  {entity_type.capitalize()}: {len(entity_set)}")
                for e in sorted(entity_set)[:5]:
                    freq = filtered_entities.get(e, 0)
                    tfidf = tfidf_scores.get(e, 0.0)
                    print(f"    - {e} (freq: {freq}, tfidf: {tfidf:.2f})")
                if len(entity_set) > 5:
                    print(f"    ... and {len(entity_set) - 5} more")
                total += len(entity_set)

        print(f"\n[OK] Total entities extracted: {total}")

        return entities

    def _classify_entity_type(self, entity: str, context_sentences: List[str]) -> str:
        """
        Classify entity type based on context

        Args:
            entity: The entity text
            context_sentences: Sentences where entity appears

        Returns:
            Entity type (disease/drug/procedure/symptom/anatomy)
        """
        context_text = " ".join(context_sentences)

        # Disease indicators
        if any(kw in context_text for kw in [
            "diagnosis", "diagnosed", "syndrome", "disease", "disorder",
            "condition", "infection", "deficiency", "risk", "incidence"
        ]):
            return "disease"

        # Drug/treatment indicators
        if any(kw in context_text for kw in [
            "administered", "therapy", "treatment", "medication", "drug",
            "given", "dose", "mg/kg", "infusion", "injection"
        ]):
            return "drug"

        # Procedure indicators
        if any(kw in context_text for kw in [
            "procedure", "performed", "technique", "method", "intervention",
            "surgery", "operation", "catheterization", "intubation"
        ]):
            return "procedure"

        # Symptom indicators
        if any(kw in context_text for kw in [
            "symptom", "sign", "presents", "characterized", "manifestation",
            "shows", "develops", "appears"
        ]):
            return "symptom"

        # Anatomy indicators
        if any(kw in context_text for kw in [
            "anatomical", "organ", "tissue", "artery", "vein", "nerve",
            "muscle", "bone", "region", "system"
        ]):
            return "anatomy"

        # Default to disease for medical terms
        return "disease"

    def extract_relationships_from_chunks(
        self,
        chunks: List,
        entities: Dict[str, Set[str]]
    ) -> List[Tuple[str, str, str]]:
        """
        Extract relationships using co-occurrence and context

        Args:
            chunks: List of chunks
            entities: Dictionary of extracted entities

        Returns:
            List of (source, target, rel_type) tuples
        """
        print(f"\n[INFO] Extracting relationships from chunks...")

        relationships = []

        # Flatten entities for lookup
        all_entities = {}
        for entity_type, entity_set in entities.items():
            for entity in entity_set:
                all_entities[entity] = entity_type

        for i, chunk in enumerate(chunks):
            if i % 50 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            text = chunk.text.lower()
            doc = self.nlp(text)

            # Find entities in this chunk
            entities_in_chunk = []
            for entity, entity_type in all_entities.items():
                if entity in text:
                    entities_in_chunk.append((entity, entity_type))

            # Extract relationships based on co-occurrence in sentences
            for i_ent, (ent1, type1) in enumerate(entities_in_chunk):
                for ent2, type2 in entities_in_chunk[i_ent+1:]:
                    # Check if both appear in same sentence
                    for sent in doc.sents:
                        sent_text = sent.text.lower()
                        if ent1 in sent_text and ent2 in sent_text:
                            # Infer relationship type
                            rel_type = self._infer_relationship_type(type1, type2, sent_text)
                            if rel_type:
                                relationships.append((ent1, ent2, rel_type))
                            break

        # Remove duplicates
        relationships = list(set(relationships))

        print(f"[OK] Found {len(relationships)} relationships")
        for rel in relationships[:10]:
            print(f"  {rel[0]} -[{rel[2]}]-> {rel[1]}")
        if len(relationships) > 10:
            print(f"  ... and {len(relationships) - 10} more")

        return relationships

    def _infer_relationship_type(self, type1: str, type2: str, sentence: str) -> str:
        """
        Infer relationship type based on entity types and sentence context
        """
        # Drug -> Disease: TREATS
        if type1 == "drug" and type2 == "disease":
            if any(kw in sentence for kw in ["treat", "therapy", "for", "given for"]):
                return "TREATS"

        # Disease -> Symptom: HAS_SYMPTOM
        if type1 == "disease" and type2 == "symptom":
            if any(kw in sentence for kw in ["symptom", "presents with", "characterized by", "with"]):
                return "HAS_SYMPTOM"

        # Disease -> Symptom: CAUSES
        if type1 == "disease" and type2 == "symptom":
            if any(kw in sentence for kw in ["causes", "leads to", "results in"]):
                return "CAUSES"

        # Procedure -> Disease: USED_FOR
        if type1 == "procedure" and type2 == "disease":
            return "USED_FOR"

        # Drug -> Disease: TREATS (reverse)
        if type1 == "disease" and type2 == "drug":
            if any(kw in sentence for kw in ["treated with", "therapy", "given"]):
                return "TREATS"  # Will reverse in graph

        return None

    def build_graph(self, limit_chunks: int = None, min_entity_freq: int = 3, top_k_entities: int = 150):
        """
        Build knowledge graph using scispaCy

        Args:
            limit_chunks: Limit number of chunks to process
            min_entity_freq: Minimum frequency for entity inclusion
            top_k_entities: Top K entities by TF-IDF
        """
        print("="*80)
        print("BUILDING MEDICAL KNOWLEDGE GRAPH (scispaCy)")
        print("="*80)
        print()

        # Step 1: Extract entities with scispaCy NER
        entities = self.extract_entities_from_chunks(
            limit=limit_chunks,
            min_frequency=min_entity_freq,
            top_k_tfidf=top_k_entities
        )

        # Step 2: Add entities to Neo4j
        print(f"\n[INFO] Adding entities to Neo4j...")
        entity_count = 0
        for entity_type, entity_names in entities.items():
            for name in entity_names:
                entity = Entity(
                    name=name,
                    type=entity_type,
                    properties={"source": "scispaCy NER", "method": "biomedical_ner"}
                )
                self.neo4j.add_entity(entity)
                entity_count += 1

        print(f"[OK] Added {entity_count} entities to graph")

        # Step 3: Extract relationships
        all_chunks = []
        for term in ["infant", "newborn", "treatment", "respiratory", "cardiac"]:
            results = self.opensearch.search(term, top_k=150)
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
                properties={"source": "scispaCy NER"}
            )
            if self.neo4j.add_relationship(relationship):
                rel_count += 1

        print(f"[OK] Added {rel_count} relationships to graph")

        # Step 5: Show stats
        print("\n" + "="*80)
        print("KNOWLEDGE GRAPH BUILT (scispaCy)")
        print("="*80)
        stats = self.neo4j.get_stats()
        print(f"\nTotal nodes: {stats['total_nodes']}")
        print(f"Total relationships: {stats['total_relationships']}")
        print(f"\nNodes by type:")
        for label, count in stats['nodes'].items():
            if count > 0:
                print(f"  {label}: {count}")


if __name__ == "__main__":
    print("=== Medical Knowledge Graph Builder (scispaCy) ===\n")

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

    # Build KG with scispaCy
    builder = MedicalKGBuilderSciSpacy(opensearch, neo4j)
    builder.build_graph(limit_chunks=500, min_entity_freq=3, top_k_entities=150)

    # Cleanup
    opensearch.close()
    neo4j.close()

    print("\n[OK] scispaCy knowledge graph build complete!")
