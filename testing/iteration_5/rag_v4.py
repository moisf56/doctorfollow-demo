"""
RAG v4: Debug Mode for GraphRAG Testing
Extends RAG v3 with debugging capabilities to show Neo4j insights

New Features:
- Shows extracted entities from query
- Shows relationships traversed in knowledge graph
- Shows answer BEFORE KG enrichment
- Shows answer AFTER KG enrichment
- Returns neo4j_insights for frontend display

Usage:
    rag = MedicalRAGv4()
    result = rag.ask_with_debug(query, language="tr", complexity="complex")

    # Returns:
    {
        "query": "...",
        "answer_before_kg": "...",  # Answer without KG enrichment
        "answer_after_kg": "...",   # Answer with KG enrichment
        "answer": "...",            # Final answer (same as answer_after_kg)
        "sources": [...],
        "kg_context": "...",
        "neo4j_insights": {
            "entities_found": ["PPHN", "nitric oxide", ...],
            "relationships_found": [
                {"entity": "PPHN", "relation": "TREATS", "target": "nitric oxide"},
                ...
            ],
            "strategy_used": "local",
            "kg_enrichment_enabled": True
        }
    }
"""
from typing import TypedDict, List, Dict, Any, Optional
from pathlib import Path
import sys

# Add parent directories for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent.parent / "iteration_2"))
sys.path.append(str(Path(__file__).parent.parent / "iteration_3"))

from iteration_3.rag_v3 import MedicalRAGv3, MedicalRAGState
from langchain_core.messages import HumanMessage


class MedicalRAGv4(MedicalRAGv3):
    """
    RAG v4: Debugging version that shows Neo4j insights

    Inherits all functionality from RAG v3, adds:
    - ask_with_debug() method that returns before/after KG answers
    - Neo4j metadata extraction (entities, relationships)
    """

    def __init__(self, *args, **kwargs):
        """Initialize RAG v4 (same as v3)"""
        super().__init__(*args, **kwargs)
        print("[OK] RAG v4 initialized (Debug Mode)")

    def ask_with_debug(
        self,
        query: str,
        language: str = "en",
        complexity: str = "simple"
    ) -> Dict[str, Any]:
        """
        Ask a question with debugging insights

        This method runs the query TWICE:
        1. WITHOUT KG enrichment (to see baseline answer)
        2. WITH KG enrichment (to see improved answer)

        Args:
            query: The medical question
            language: 'en' or 'tr'
            complexity: 'simple' or 'complex'

        Returns:
            dict with answer_before_kg, answer_after_kg, neo4j_insights, etc.
        """
        print("\n" + "="*80)
        print("[DEBUG MODE] Running query with Neo4j insights")
        print("="*80)

        # Step 1: Run WITHOUT KG enrichment (force simple complexity)
        print("\n[STEP 1/2] Generating answer WITHOUT knowledge graph...")
        result_without_kg = self._ask_without_kg(query, language)
        answer_before_kg = result_without_kg["answer"]

        # Step 2: Run WITH KG enrichment (use provided complexity)
        print("\n[STEP 2/2] Generating answer WITH knowledge graph...")
        result_with_kg = self._ask_with_kg(query, language, complexity)
        answer_after_kg = result_with_kg["answer"]
        kg_context = result_with_kg.get("kg_context", "")

        # Step 3: Extract Neo4j insights from KG context
        neo4j_insights = self._extract_neo4j_insights(
            query=query,
            chunks=result_with_kg["sources"],
            kg_context=kg_context,
            complexity=complexity
        )

        print("\n[DEBUG] Neo4j Insights:")
        print(f"  - Entities found: {len(neo4j_insights['entities_found'])}")
        print(f"  - Relationships: {len(neo4j_insights['relationships_found'])}")
        print(f"  - Strategy: {neo4j_insights['strategy_used']}")
        print(f"  - KG enrichment: {neo4j_insights['kg_enrichment_enabled']}")

        return {
            "query": query,
            "answer_before_kg": answer_before_kg,
            "answer_after_kg": answer_after_kg,
            "answer": answer_after_kg,  # Final answer is the KG-enriched one
            "sources": result_with_kg["sources"],
            "kg_context": kg_context,
            "num_sources": len(result_with_kg["sources"]),
            "neo4j_insights": neo4j_insights
        }

    def _ask_without_kg(self, query: str, language: str) -> Dict[str, Any]:
        """
        Run query WITHOUT KG enrichment (force simple complexity)
        """
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "query_language": language,
            "query_complexity": "simple",  # Force simple to skip KG
            "bm25_chunks": [],
            "semantic_chunks": [],
            "fused_chunks": [],
            "kg_context": "",
            "answer": "",
            "sources": []
        }

        final_state = self.graph.invoke(initial_state)

        return {
            "query": query,
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "kg_context": final_state.get("kg_context", ""),
            "num_sources": len(final_state["sources"])
        }

    def _ask_with_kg(self, query: str, language: str, complexity: str) -> Dict[str, Any]:
        """
        Run query WITH KG enrichment (force complex complexity)
        """
        # Force complexity to "complex" to ensure KG enrichment runs
        if complexity == "simple":
            complexity = "complex"

        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "query_language": language,
            "query_complexity": complexity,  # Force complex to enable KG
            "bm25_chunks": [],
            "semantic_chunks": [],
            "fused_chunks": [],
            "kg_context": "",
            "answer": "",
            "sources": []
        }

        final_state = self.graph.invoke(initial_state)

        return {
            "query": query,
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "kg_context": final_state.get("kg_context", ""),
            "num_sources": len(final_state["sources"])
        }

    def _extract_neo4j_insights(
        self,
        query: str,
        chunks: List[Dict],
        kg_context: str,
        complexity: str
    ) -> Dict[str, Any]:
        """
        Extract debugging insights from Neo4j operations

        This analyzes what the KG expander did:
        - Which entities were found
        - Which relationships were traversed
        - What strategy was used
        """
        # Extract entities using the KG expander's method (if it has the method)
        entities = []
        try:
            if hasattr(self.kg_expander, '_extract_entity_names'):
                entities = self.kg_expander._extract_entity_names(query, chunks)
        except Exception as e:
            print(f"[DEBUG] Could not extract entities: {e}")
            entities = []

        # Parse relationships from kg_context
        relationships = self._parse_relationships_from_context(kg_context)

        # Determine strategy used
        strategy = "local"  # Default
        try:
            if hasattr(self.kg_expander, '_detect_query_strategy'):
                strategy = self.kg_expander._detect_query_strategy(query, chunks)
        except Exception as e:
            print(f"[DEBUG] Could not detect strategy: {e}")

        # Check if KG was actually used
        kg_enabled = complexity in ["complex", "complex_reasoning"]

        return {
            "entities_found": entities[:10] if entities else [],  # Limit to 10 for display
            "relationships_found": relationships,
            "strategy_used": strategy,
            "kg_enrichment_enabled": kg_enabled,
            "kg_context_length": len(kg_context) if kg_context else 0
        }

    def _parse_relationships_from_context(self, kg_context: str) -> List[Dict[str, str]]:
        """
        Parse relationship information from KG context string

        Example kg_context:
            Entity: PPHN (Condition)
              TREATS: nitric oxide (Drug)
              AFFECTS: pulmonary vessels (Anatomy)

        Returns:
            [
                {"entity": "PPHN", "relation": "TREATS", "target": "nitric oxide"},
                {"entity": "PPHN", "relation": "AFFECTS", "target": "pulmonary vessels"},
                ...
            ]
        """
        relationships = []

        if not kg_context:
            return relationships

        lines = kg_context.split('\n')
        current_entity = None

        for line in lines:
            # Check if this is an entity line (e.g., "Entity: PPHN (Condition)")
            if line.strip().startswith("Entity:"):
                # Extract entity name
                parts = line.split("Entity:")
                if len(parts) > 1:
                    entity_part = parts[1].strip()
                    # Extract just the name before (Type)
                    if "(" in entity_part:
                        current_entity = entity_part.split("(")[0].strip()
                    else:
                        current_entity = entity_part

            # Check if this is a relationship line (e.g., "  TREATS: nitric oxide (Drug)")
            elif ":" in line and line.strip() and current_entity:
                # Skip certain lines
                if "Knowledge Graph Context" in line or "End of" in line or "Related (2-hop)" in line:
                    continue

                # Extract relationship type and target
                parts = line.split(":", 1)
                if len(parts) == 2:
                    relation_type = parts[0].strip()
                    target_part = parts[1].strip()

                    # Parse targets (might be multiple comma-separated)
                    targets = target_part.split(",")
                    for target in targets[:3]:  # Limit to 3 per relation
                        target = target.strip()
                        # Remove type annotation if present (e.g., "(Drug)")
                        if "(" in target:
                            target = target.split("(")[0].strip()

                        # Skip empty targets
                        if target and target != "...":
                            relationships.append({
                                "entity": current_entity,
                                "relation": relation_type,
                                "target": target
                            })

        return relationships[:20]  # Limit to 20 relationships for display


if __name__ == "__main__":
    """Test RAG v4 debug mode"""
    print("="*80)
    print("RAG v4 - Debug Mode Test")
    print("="*80)
    print()

    # Initialize
    rag = MedicalRAGv4()

    # Test query (Turkish medical query)
    query = "35 haftalık bir prematüre bebekte postnatal 3. günde apne epizodları görülüyor. Bu durumun en olası nedeni nedir ve hangi tedavi önerilir?"

    print("\n" + "="*80)
    print(f"QUERY: {query}")
    print("="*80)

    # Ask with debug mode
    result = rag.ask_with_debug(query, language="tr", complexity="complex")

    # Display results
    print("\n" + "="*80)
    print("[ANSWER BEFORE KG ENRICHMENT]")
    print("="*80)
    print(result["answer_before_kg"][:500] + "..." if len(result["answer_before_kg"]) > 500 else result["answer_before_kg"])

    print("\n" + "="*80)
    print("[ANSWER AFTER KG ENRICHMENT]")
    print("="*80)
    print(result["answer_after_kg"][:500] + "..." if len(result["answer_after_kg"]) > 500 else result["answer_after_kg"])

    print("\n" + "="*80)
    print("[NEO4J INSIGHTS]")
    print("="*80)
    insights = result["neo4j_insights"]
    print(f"Strategy Used: {insights['strategy_used']}")
    print(f"KG Enrichment Enabled: {insights['kg_enrichment_enabled']}")
    print(f"\nEntities Found ({len(insights['entities_found'])}):")
    for entity in insights['entities_found']:
        print(f"  - {entity}")

    print(f"\nRelationships Traversed ({len(insights['relationships_found'])}):")
    for rel in insights['relationships_found'][:10]:  # Show first 10
        print(f"  - {rel['entity']} --[{rel['relation']}]--> {rel['target']}")

    print(f"\n[SOURCES] ({result['num_sources']} sources)")
    for i, source in enumerate(result['sources'], 1):
        print(f"  {i}. Page {source['page_number']} - RRF: {source['rrf_score']:.4f}")

    print("\n" + "="*80)
    print("Test Complete!")
    print("="*80)
