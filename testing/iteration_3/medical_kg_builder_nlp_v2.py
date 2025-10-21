"""
Medical Knowledge Graph Builder with Data-Driven NLP
No hardcoded entities - uses linguistic analysis + frequency filtering

Approach:
1. Extract noun phrases using spaCy's parser
2. Classify entity types using POS patterns and context
3. Filter by TF-IDF / frequency to remove noise
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


class MedicalKGBuilderNLPv2:
    """
    Build medical knowledge graph using data-driven NLP

    No hardcoded lists - entities extracted via:
    - Noun phrase chunking
    - POS tagging and dependency parsing
    - TF-IDF scoring for filtering
    - Context-based type inference
    """

    def __init__(self, opensearch_store: OpenSearchStore, neo4j_store: Neo4jStore):
        """
        Initialize KG builder with data-driven NLP

        Args:
            opensearch_store: OpenSearch store with indexed chunks
            neo4j_store: Neo4j store for graph
        """
        self.opensearch = opensearch_store
        self.neo4j = neo4j_store

        # Load spaCy model
        print("[Loading] spaCy NLP model...")
        try:
            self.nlp = spacy.load("en_core_web_sm")
            print("[OK] Loaded en_core_web_sm")
        except OSError:
            print("[ERROR] No spaCy model found. Please run:")
            print("  python -m spacy download en_core_web_sm")
            raise

        # Medical context keywords for type inference
        # These are used ONLY for classification, not for entity extraction
        self.type_context_keywords = {
            "disease": ["diagnosis", "disease", "syndrome", "disorder", "condition", "infection"],
            "drug": ["treatment", "therapy", "administered", "medication", "drug", "given"],
            "procedure": ["procedure", "technique", "method", "performed", "intervention"],
            "symptom": ["symptom", "sign", "presents", "characterized", "manifestation"],
            "anatomy": ["anatomical", "organ", "tissue", "system", "region"]
        }

    def extract_noun_phrases(self, chunks: List, min_freq: int = 2) -> Dict[str, int]:
        """
        Extract noun phrases using spaCy's parser

        Args:
            chunks: List of text chunks
            min_freq: Minimum frequency for a phrase to be included

        Returns:
            Dictionary of noun_phrase -> frequency
        """
        print(f"[INFO] Extracting noun phrases from {len(chunks)} chunks...")

        phrase_counter = Counter()

        for i, chunk in enumerate(chunks):
            if i % 50 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            doc = self.nlp(chunk.text)

            # Extract noun chunks
            for np in doc.noun_chunks:
                # Clean and normalize
                phrase = np.text.lower().strip()

                # Filter out very short phrases, numbers, pronouns
                if len(phrase) < 4 or phrase.isdigit() or np.root.pos_ in ["PRON", "DET"]:
                    continue

                # Count phrase
                phrase_counter[phrase] += 1

        # Filter by frequency
        filtered = {phrase: count for phrase, count in phrase_counter.items() if count >= min_freq}

        print(f"[OK] Extracted {len(filtered)} noun phrases (freq >= {min_freq})")
        return filtered

    def calculate_tfidf(self, noun_phrases: Dict[str, int], chunks: List) -> Dict[str, float]:
        """
        Calculate TF-IDF scores for noun phrases

        Args:
            noun_phrases: Dictionary of phrase -> frequency
            chunks: List of chunks

        Returns:
            Dictionary of phrase -> TF-IDF score
        """
        print("[INFO] Calculating TF-IDF scores...")

        # Document frequency (how many chunks contain each phrase)
        df = Counter()
        total_chunks = len(chunks)

        for chunk in chunks:
            text = chunk.text.lower()
            phrases_in_chunk = set()
            for phrase in noun_phrases.keys():
                if phrase in text:
                    phrases_in_chunk.add(phrase)
            df.update(phrases_in_chunk)

        # Calculate TF-IDF
        tfidf = {}
        for phrase, tf in noun_phrases.items():
            if phrase in df:
                idf = log(total_chunks / df[phrase])
                tfidf[phrase] = tf * idf
            else:
                tfidf[phrase] = 0.0

        print("[OK] TF-IDF calculated")
        return tfidf

    def classify_entity_type(self, phrase: str, context_sentences: List[str]) -> str:
        """
        Classify entity type based on context

        Args:
            phrase: The entity phrase
            context_sentences: Sentences where phrase appears

        Returns:
            Entity type (disease/drug/procedure/symptom/anatomy)
        """
        # Count context keywords
        type_scores = defaultdict(int)

        for sentence in context_sentences:
            sentence_lower = sentence.lower()
            for entity_type, keywords in self.type_context_keywords.items():
                for keyword in keywords:
                    if keyword in sentence_lower:
                        type_scores[entity_type] += 1

        # Return type with highest score, default to disease
        if type_scores:
            return max(type_scores, key=type_scores.get)
        return "disease"  # Default

    def extract_entities_from_chunks(
        self,
        limit: int = None,
        min_frequency: int = 2,
        top_k_tfidf: int = 100
    ) -> Dict[str, Set[str]]:
        """
        Extract medical entities using data-driven NLP

        Args:
            limit: Maximum number of chunks to process
            min_frequency: Minimum frequency for entity inclusion
            top_k_tfidf: Top K entities by TF-IDF score

        Returns:
            Dictionary of entity_type -> set of entity names
        """
        print(f"[INFO] Extracting entities with data-driven NLP...")

        # Get chunks
        all_chunks = []
        for term in ["infant", "newborn", "neonatal", "treatment", "disease"]:
            results = self.opensearch.search(term, top_k=200)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit] if limit else list(unique_chunks)

        print(f"[OK] Processing {len(chunks)} chunks")

        # Step 1: Extract noun phrases
        noun_phrases = self.extract_noun_phrases(chunks, min_freq=min_frequency)

        # Step 2: Calculate TF-IDF
        tfidf_scores = self.calculate_tfidf(noun_phrases, chunks)

        # Step 3: Select top K by TF-IDF
        sorted_phrases = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)
        top_phrases = [phrase for phrase, score in sorted_phrases[:top_k_tfidf]]

        print(f"[INFO] Selected top {len(top_phrases)} phrases by TF-IDF")

        # Step 4: Classify each phrase's entity type
        entities = {
            "disease": set(),
            "drug": set(),
            "procedure": set(),
            "symptom": set(),
            "anatomy": set()
        }

        # Find context sentences for each phrase
        phrase_contexts = defaultdict(list)
        for chunk in chunks:
            for phrase in top_phrases:
                if phrase in chunk.text.lower():
                    # Get sentences containing the phrase
                    doc = self.nlp(chunk.text)
                    for sent in doc.sents:
                        if phrase in sent.text.lower():
                            phrase_contexts[phrase].append(sent.text)

        # Classify each phrase
        print("[INFO] Classifying entity types...")
        for phrase in top_phrases:
            context = phrase_contexts.get(phrase, [])
            entity_type = self.classify_entity_type(phrase, context)
            entities[entity_type].add(phrase)

        # Print stats
        print(f"\n[ENTITIES EXTRACTED]")
        total = 0
        for entity_type, entity_set in entities.items():
            if entity_set:
                print(f"  {entity_type.capitalize()}: {len(entity_set)}")
                for e in sorted(entity_set)[:5]:
                    freq = noun_phrases.get(e, 0)
                    tfidf = tfidf_scores.get(e, 0.0)
                    print(f"    - {e} (freq: {freq}, tfidf: {tfidf:.2f})")
                if len(entity_set) > 5:
                    print(f"    ... and {len(entity_set) - 5} more")
                total += len(entity_set)

        print(f"\n[OK] Total entities extracted: {total}")

        return entities

    def extract_relationships_from_chunks(
        self,
        chunks: List,
        entities: Dict[str, Set[str]]
    ) -> List[Tuple[str, str, str]]:
        """
        Extract relationships using dependency parsing and co-occurrence

        Args:
            chunks: List of chunks
            entities: Dictionary of extracted entities

        Returns:
            List of (source, target, rel_type) tuples
        """
        print(f"\n[INFO] Extracting relationships with NLP...")

        relationships = []

        # Flatten entities for easier lookup
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

            # Extract relationships based on co-occurrence and context
            for i, (ent1, type1) in enumerate(entities_in_chunk):
                for ent2, type2 in entities_in_chunk[i+1:]:
                    # Check if both appear in same sentence
                    for sent in doc.sents:
                        sent_text = sent.text.lower()
                        if ent1 in sent_text and ent2 in sent_text:
                            # Infer relationship type based on entity types
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

        Args:
            type1: First entity type
            type2: Second entity type
            sentence: Sentence containing both entities

        Returns:
            Relationship type or None
        """
        # Drug -> Disease: TREATS
        if type1 == "drug" and type2 == "disease":
            if any(kw in sentence for kw in ["treat", "therapy", "for", "given"]):
                return "TREATS"

        # Disease -> Symptom: HAS_SYMPTOM
        if type1 == "disease" and type2 == "symptom":
            if any(kw in sentence for kw in ["symptom", "presents", "characterized"]):
                return "HAS_SYMPTOM"

        # Disease -> Symptom: CAUSES
        if type1 == "disease" and type2 == "symptom":
            if any(kw in sentence for kw in ["causes", "leads to", "results"]):
                return "CAUSES"

        # Procedure -> Disease: USED_FOR
        if type1 == "procedure" and type2 == "disease":
            if any(kw in sentence for kw in ["for", "treatment", "management"]):
                return "USED_FOR"

        # Procedure -> Disease: TREATS (alternative)
        if type1 == "procedure" and type2 == "disease":
            return "USED_FOR"

        return None

    def build_graph(self, limit_chunks: int = None, min_entity_freq: int = 2, top_k_entities: int = 100):
        """
        Build knowledge graph using data-driven NLP

        Args:
            limit_chunks: Limit number of chunks to process
            min_entity_freq: Minimum frequency for entity inclusion
            top_k_entities: Top K entities by TF-IDF
        """
        print("="*80)
        print("BUILDING MEDICAL KNOWLEDGE GRAPH (Data-Driven NLP)")
        print("="*80)
        print()

        # Step 1: Extract entities with data-driven NLP
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
                    properties={"source": "Data-driven NLP", "method": "noun_phrase + tfidf"}
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
                properties={"source": "Data-driven NLP"}
            )
            if self.neo4j.add_relationship(relationship):
                rel_count += 1

        print(f"[OK] Added {rel_count} relationships to graph")

        # Step 5: Show stats
        print("\n" + "="*80)
        print("KNOWLEDGE GRAPH BUILT (Data-Driven NLP)")
        print("="*80)
        stats = self.neo4j.get_stats()
        print(f"\nTotal nodes: {stats['total_nodes']}")
        print(f"Total relationships: {stats['total_relationships']}")
        print(f"\nNodes by type:")
        for label, count in stats['nodes'].items():
            if count > 0:
                print(f"  {label}: {count}")


if __name__ == "__main__":
    print("=== Medical Knowledge Graph Builder (Data-Driven NLP) ===\n")

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

    # Build KG with data-driven NLP
    builder = MedicalKGBuilderNLPv2(opensearch, neo4j)
    builder.build_graph(limit_chunks=500, min_entity_freq=2, top_k_entities=100)

    # Cleanup
    opensearch.close()
    neo4j.close()

    print("\n[OK] Data-driven NLP knowledge graph build complete!")
