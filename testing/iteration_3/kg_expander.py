"""
Knowledge Graph Expander for Query-Time Enrichment
Extracts entities from queries/chunks and enriches with graph context
"""
import re
from typing import List, Dict, Set, Any
from neo4j_store import Neo4jStore


class KGExpander:
    """
    Expand retrieval results with knowledge graph context

    Workflow:
    1. Extract entities from query and retrieved chunks
    2. Find related entities in the graph (multi-hop)
    3. Generate enriched context for LLM
    """

    def __init__(self, neo4j_store: Neo4jStore, entity_patterns: Dict[str, List[str]] = None):
        """
        Initialize KG expander

        Args:
            neo4j_store: Neo4j store with medical knowledge graph
            entity_patterns: Optional dict of entity patterns from KG builder
        """
        self.neo4j = neo4j_store

        # Build comprehensive entity keywords set
        if entity_patterns:
            # Use provided entity patterns (from medical_kg_builder)
            self.entity_keywords = set()
            for entity_type, entities in entity_patterns.items():
                self.entity_keywords.update(entities)
        else:
            # Fallback to core entities (for backward compatibility)
            self.entity_keywords = {
                "PPHN", "PDA", "RDS", "apnea", "hyperthyroidism", "sepsis",
                "pneumonia", "acyclovir", "penicillin", "oxygen", "ECMO",
                "cardiac massage", "intubation", "ventilation",
                "respiratory distress", "bradycardia", "hypoxia",
                "ductus arteriosus", "pulmonary artery"
            }

    def extract_entities_from_text(self, text: str) -> Set[str]:
        """
        Extract medical entities from text

        Args:
            text: Text to extract from

        Returns:
            Set of entity names found
        """
        text_lower = text.lower()
        found_entities = set()

        for entity in self.entity_keywords:
            if entity.lower() in text_lower:
                found_entities.add(entity)

        return found_entities

    def expand_with_graph(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        max_hops: int = 2,
        max_related: int = 5
    ) -> str:
        """
        Expand query and chunks with knowledge graph context

        Args:
            query: User query
            retrieved_chunks: List of retrieved chunks
            max_hops: Maximum graph traversal hops
            max_related: Maximum related entities to include

        Returns:
            Knowledge graph context as text
        """
        # Step 1: Extract entities from query
        query_entities = self.extract_entities_from_text(query)

        # Step 2: Extract entities from chunks
        chunk_entities = set()
        for chunk in retrieved_chunks:
            chunk_text = chunk.get("text", "")
            chunk_entities.update(self.extract_entities_from_text(chunk_text))

        all_entities = query_entities | chunk_entities

        if not all_entities:
            return ""  # No entities found

        # Step 3: Find related entities in graph
        kg_context_parts = []
        kg_context_parts.append("=== KNOWLEDGE GRAPH CONTEXT ===\n")

        for entity in all_entities:
            # Get entity context from graph
            entity_context = self.neo4j.get_entity_context(entity)

            if entity_context and "No information found" not in entity_context:
                kg_context_parts.append(f"\n{entity_context}")

            # Find related entities
            related = self.neo4j.find_related_entities(
                entity,
                max_hops=max_hops,
                limit=max_related
            )

            if related:
                related_names = [r["name"] for r in related[:3]]  # Top 3
                kg_context_parts.append(f"  Related to: {', '.join(related_names)}")

        if len(kg_context_parts) == 1:  # Only header
            return ""

        kg_context_parts.append("\n=== END KNOWLEDGE GRAPH CONTEXT ===\n")

        return "\n".join(kg_context_parts)

    def get_treatment_context(self, disease: str) -> str:
        """
        Get treatment information for a disease from graph

        Args:
            disease: Disease name

        Returns:
            Treatment context text
        """
        treatments = self.neo4j.find_treatment_for(disease)

        if not treatments:
            return ""

        context = f"\nKnown treatments for {disease}:\n"
        for treatment in treatments:
            context += f"  - {treatment['name']} ({treatment['type']})\n"

        return context

    def get_symptom_context(self, disease: str) -> str:
        """
        Get symptom information for a disease from graph

        Args:
            disease: Disease name

        Returns:
            Symptom context text
        """
        symptoms = self.neo4j.find_symptoms_of(disease)

        if not symptoms:
            return ""

        context = f"\nKnown symptoms of {disease}:\n"
        for symptom in symptoms:
            context += f"  - {symptom}\n"

        return context


if __name__ == "__main__":
    # Test KG expander
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config import settings

    print("=== KG Expander Test ===\n")

    # Connect to Neo4j
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    expander = KGExpander(neo4j)

    # Test 1: Extract entities from query
    print("[TEST 1] Extract entities from query")
    query = "What is the treatment for PPHN in newborns?"
    entities = expander.extract_entities_from_text(query)
    print(f"Query: {query}")
    print(f"Entities found: {entities}\n")

    # Test 2: Expand with graph context
    print("[TEST 2] Expand with graph context")
    test_chunks = [
        {"text": "PPHN is characterized by respiratory distress and hypoxia"},
        {"text": "Treatment may include oxygen therapy and ECMO"}
    ]

    kg_context = expander.expand_with_graph(query, test_chunks, max_hops=2)
    print(kg_context)

    # Test 3: Get treatment context
    print("\n[TEST 3] Get treatment context for PPHN")
    treatment_context = expander.get_treatment_context("PPHN")
    print(treatment_context)

    # Test 4: Get symptom context
    print("[TEST 4] Get symptom context for PPHN")
    symptom_context = expander.get_symptom_context("PPHN")
    print(symptom_context)

    neo4j.close()
    print("\n[OK] Test complete!")
