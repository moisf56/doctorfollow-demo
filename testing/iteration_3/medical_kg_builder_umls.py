"""
Medical Knowledge Graph Builder with UMLS Entity Linking
Gold standard approach: scispaCy NER + UMLS EntityLinker

Features:
- Extract entities with scispaCy medical NER
- Link entities to UMLS concepts (CUIs)
- Use UMLS semantic types for accurate classification
- No manual classification - fully data-driven
"""
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from collections import Counter, defaultdict
import spacy
from scispacy.linking import EntityLinker
from math import log

sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import OpenSearchStore
from neo4j_store import Neo4jStore


class MedicalKGBuilderUMLS:
    """
    Build medical knowledge graph using UMLS entity linking

    Gold standard approach:
    - scispaCy NER for biomedical entity extraction
    - UMLS EntityLinker for concept normalization
    - UMLS semantic types for entity classification
    - Relationship extraction with context
    """

    def __init__(self, opensearch_store: OpenSearchStore, neo4j_store: Neo4jStore):
        """Initialize KG builder with UMLS"""
        self.opensearch = opensearch_store
        self.neo4j = neo4j_store

        # Load scispaCy model
        print("[Loading] scispaCy medical NLP model...")
        try:
            self.nlp = spacy.load("en_core_sci_sm")
            print("[OK] Loaded en_core_sci_sm")
        except OSError:
            print("[ERROR] scispaCy model not found")
            raise

        # Add UMLS EntityLinker to pipeline
        print("[Loading] UMLS EntityLinker (this may take a while on first run)...")
        print("  - Downloading 1GB knowledge base if not cached")
        print("  - This is a one-time download")

        self.nlp.add_pipe("scispacy_linker", config={"resolve_abbreviations": True, "linker_name": "umls"})

        print("[OK] UMLS EntityLinker loaded")

        # UMLS semantic type mapping to our schema
        # See: https://lhncbc.nlm.nih.gov/ii/tools/MetaMap/Docs/SemGroups_2018.txt
        self.semantic_type_map = {
            # Disorders
            "T047": "disease",  # Disease or Syndrome
            "T048": "disease",  # Mental or Behavioral Dysfunction
            "T049": "disease",  # Cell or Molecular Dysfunction
            "T050": "disease",  # Experimental Model of Disease
            "T191": "disease",  # Neoplastic Process
            "T046": "disease",  # Pathologic Function

            # Chemicals & Drugs
            "T116": "drug",  # Amino Acid, Peptide, or Protein
            "T195": "drug",  # Antibiotic
            "T123": "drug",  # Biologically Active Substance
            "T122": "drug",  # Biomedical or Dental Material
            "T103": "drug",  # Chemical
            "T120": "drug",  # Chemical Viewed Functionally
            "T104": "drug",  # Chemical Viewed Structurally
            "T200": "drug",  # Clinical Drug
            "T126": "drug",  # Enzyme
            "T125": "drug",  # Hormone
            "T129": "drug",  # Immunologic Factor
            "T130": "drug",  # Indicator, Reagent, or Diagnostic Aid
            "T197": "drug",  # Inorganic Chemical
            "T114": "drug",  # Nucleic Acid, Nucleoside, or Nucleotide
            "T109": "drug",  # Organic Chemical
            "T121": "drug",  # Pharmacologic Substance
            "T192": "drug",  # Receptor
            "T127": "drug",  # Vitamin

            # Procedures
            "T060": "procedure",  # Diagnostic Procedure
            "T061": "procedure",  # Therapeutic or Preventive Procedure
            "T058": "procedure",  # Health Care Activity
            "T059": "procedure",  # Laboratory Procedure
            "T063": "procedure",  # Molecular Biology Research Technique
            "T062": "procedure",  # Research Activity

            # Findings (Symptoms/Signs)
            "T184": "symptom",  # Sign or Symptom
            "T033": "symptom",  # Finding
            "T034": "symptom",  # Laboratory or Test Result

            # Anatomy
            "T017": "anatomy",  # Anatomical Structure
            "T029": "anatomy",  # Body Location or Region
            "T023": "anatomy",  # Body Part, Organ, or Organ Component
            "T030": "anatomy",  # Body Space or Junction
            "T031": "anatomy",  # Body Substance
            "T022": "anatomy",  # Body System
            "T025": "anatomy",  # Cell
            "T026": "anatomy",  # Cell Component
            "T018": "anatomy",  # Embryonic Structure
            "T021": "anatomy",  # Fully Formed Anatomical Structure
            "T024": "anatomy",  # Tissue
        }

    def extract_entities_from_chunks(
        self,
        limit: int = None,
        min_frequency: int = 3,
        top_k_tfidf: int = 150
    ) -> Dict[str, Set[Tuple[str, str]]]:
        """
        Extract and classify medical entities using UMLS

        Returns:
            Dictionary of entity_type -> set of (entity_name, cui) tuples
        """
        print(f"[INFO] Extracting medical entities with UMLS linking...")

        # Get chunks
        all_chunks = []
        search_terms = [
            "infant", "newborn", "neonatal", "treatment", "disease",
            "respiratory", "cardiac", "therapy", "sepsis"
        ]
        for term in search_terms:
            results = self.opensearch.search(term, top_k=100)
            all_chunks.extend(results)

        unique_chunks = {c.chunk_id: c for c in all_chunks}.values()
        chunks = list(unique_chunks)[:limit] if limit else list(unique_chunks)

        print(f"[OK] Processing {len(chunks)} chunks with UMLS linking...")

        # Extract entities with UMLS linking
        entity_info = defaultdict(lambda: {"count": 0, "cui": None, "sem_types": set()})

        print("[INFO] Running NER + UMLS linking (this will take a few minutes)...")
        for i, chunk in enumerate(chunks):
            if i % 20 == 0 and i > 0:
                print(f"  Processed {i}/{len(chunks)} chunks...")

            doc = self.nlp(chunk.text)

            for ent in doc.ents:
                # Normalize entity text
                entity_text = ent.text.lower().strip()

                # Filter noise
                if len(entity_text) < 3 or entity_text.isdigit():
                    continue
                if entity_text in ["the", "a", "an", "this", "that", "fig", "table", "etc"]:
                    continue

                # Get UMLS linking info
                if ent._.kb_ents:  # Successfully linked to UMLS
                    cui, score = ent._.kb_ents[0]  # Top match

                    # Get semantic types for this CUI
                    linker = self.nlp.get_pipe("scispacy_linker")
                    umls_entity = linker.kb.cui_to_entity.get(cui)

                    if umls_entity:
                        sem_types = umls_entity.types

                        entity_info[entity_text]["count"] += 1
                        entity_info[entity_text]["cui"] = cui
                        entity_info[entity_text]["sem_types"].update(sem_types)

        # Filter by frequency
        filtered_entities = {
            entity: info
            for entity, info in entity_info.items()
            if info["count"] >= min_frequency
        }

        print(f"[OK] Found {len(filtered_entities)} UMLS-linked entities (freq >= {min_frequency})")

        # Calculate TF-IDF
        print("[INFO] Calculating TF-IDF scores...")
        entity_freq = {e: info["count"] for e, info in filtered_entities.items()}

        df = Counter()
        total_chunks = len(chunks)
        for chunk in chunks:
            text = chunk.text.lower()
            for entity in filtered_entities.keys():
                if entity in text:
                    df[entity] += 1

        tfidf_scores = {}
        for entity in filtered_entities.keys():
            tf = entity_freq[entity]
            if entity in df and df[entity] > 0:
                idf = log(total_chunks / df[entity])
                tfidf_scores[entity] = tf * idf
            else:
                tfidf_scores[entity] = 0.0

        # Select top K by TF-IDF
        sorted_entities = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)
        top_entity_names = {entity for entity, score in sorted_entities[:top_k_tfidf]}

        # Classify using UMLS semantic types
        print("[INFO] Classifying entities using UMLS semantic types...")
        classified_entities = {
            "disease": set(),
            "drug": set(),
            "procedure": set(),
            "symptom": set(),
            "anatomy": set()
        }

        for entity in top_entity_names:
            info = filtered_entities[entity]
            cui = info["cui"]
            sem_types = info["sem_types"]

            # Map to our schema using semantic types
            entity_type = self._classify_by_semantic_types(sem_types)
            if entity_type:
                classified_entities[entity_type].add((entity, cui))

        # Print stats
        print(f"\n[ENTITIES CLASSIFIED with UMLS]")
        total = 0
        for entity_type, entity_set in classified_entities.items():
            if entity_set:
                print(f"  {entity_type.capitalize()}: {len(entity_set)}")
                for entity, cui in sorted(entity_set)[:5]:
                    freq = entity_freq.get(entity, 0)
                    tfidf = tfidf_scores.get(entity, 0.0)
                    print(f"    - {entity} (CUI: {cui}, freq: {freq}, tfidf: {tfidf:.2f})")
                if len(entity_set) > 5:
                    print(f"    ... and {len(entity_set) - 5} more")
                total += len(entity_set)

        print(f"\n[OK] Total entities classified: {total}")

        return classified_entities

    def _classify_by_semantic_types(self, sem_types: Set[str]) -> str:
        """
        Classify entity based on UMLS semantic types

        Args:
            sem_types: Set of UMLS semantic type codes (e.g., {"T047", "T184"})

        Returns:
            Entity type from our schema, or None
        """
        # Count votes for each type
        type_votes = defaultdict(int)

        for sem_type in sem_types:
            if sem_type in self.semantic_type_map:
                entity_type = self.semantic_type_map[sem_type]
                type_votes[entity_type] += 1

        if type_votes:
            # Return type with most votes
            return max(type_votes, key=type_votes.get)

        return None  # Unclassified

    def build_graph(
        self,
        limit_chunks: int = None,
        min_entity_freq: int = 3,
        top_k_entities: int = 150
    ):
        """Build knowledge graph using UMLS"""
        print("="*80)
        print("BUILDING MEDICAL KNOWLEDGE GRAPH (UMLS)")
        print("="*80)
        print()

        # Extract and classify entities with UMLS
        entities = self.extract_entities_from_chunks(
            limit=limit_chunks,
            min_frequency=min_entity_freq,
            top_k_tfidf=top_k_entities
        )

        # Add entities to Neo4j with UMLS CUIs
        print(f"\n[INFO] Adding entities to Neo4j with UMLS metadata...")
        entity_count = 0

        for entity_type, entity_set in entities.items():
            for entity_name, cui in entity_set:
                query = """
                MERGE (e {name: $name})
                SET e :MedicalEntity
                SET e.type = $entity_type
                SET e.umls_cui = $cui
                SET e.source = 'UMLS'
                """
                with self.neo4j.driver.session() as session:
                    session.run(query, name=entity_name, entity_type=entity_type, cui=cui)
                entity_count += 1

        print(f"[OK] Added {entity_count} UMLS-linked entities to graph")

        print("\n" + "="*80)
        print("KNOWLEDGE GRAPH BUILT (UMLS)")
        print("="*80)
        print(f"\nTotal entities: {entity_count}")
        for entity_type, entity_set in entities.items():
            if entity_set:
                print(f"  {entity_type.capitalize()}: {len(entity_set)}")


if __name__ == "__main__":
    print("=== Medical Knowledge Graph Builder (UMLS) ===\n")

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

    # Build UMLS-based KG
    builder = MedicalKGBuilderUMLS(opensearch, neo4j)
    builder.build_graph(
        limit_chunks=300,  # Smaller for UMLS (it's slower)
        min_entity_freq=3,
        top_k_entities=150
    )

    # Cleanup
    opensearch.close()
    neo4j.close()

    print("\n[OK] UMLS knowledge graph build complete!")
