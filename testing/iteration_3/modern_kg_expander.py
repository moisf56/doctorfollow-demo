"""
Modern Knowledge Graph Query Enhancement
Implements state-of-the-art GraphRAG strategies (2024-2025)

Based on:
- Microsoft GraphRAG (Local + Global Search)
- Neo4j LLM Graph Builder patterns
- Your new graph structure with SIMILAR relationships

Key Strategies:
1. Local Search: Entity-focused with multi-hop traversal
2. Global Search: Community-based summaries (if communities exist)
3. Hybrid Search: Combine both strategies
4. Semantic Chunk Navigation: Use SIMILAR relationships
"""
from typing import List, Dict, Any, Optional
from neo4j_store import Neo4jStore
import re
import time
from neo4j.exceptions import ServiceUnavailable, SessionExpired


class ModernKGExpander:
    """
    Modern GraphRAG query enhancement using your LLM-generated graph

    Your graph structure:
    - Nodes: Condition (220), Chemical (5), Complication (6), etc.
    - Relationships: AFFECTS, ADMINISTERED_TO, SIMILAR, etc.
    - Document structure: Document -> Chunks (PART_OF, NEXT_CHUNK, SIMILAR)
    """

    def __init__(self, neo4j_store: Neo4jStore, llm=None):
        self.neo4j = neo4j_store
        self.llm = llm  # LLM for entity extraction

    def _retry_neo4j_query(self, func, *args, max_retries=3, **kwargs):
        """
        Retry Neo4j queries with exponential backoff for transient connection failures

        Args:
            func: The function to execute
            max_retries: Maximum number of retry attempts
            *args, **kwargs: Arguments to pass to func

        Returns:
            Result from func or None if all retries fail
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (ServiceUnavailable, SessionExpired) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"  [RETRY] Neo4j connection error (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  [ERROR] Neo4j connection failed after {max_retries} attempts: {e}")
                    return None
            except Exception as e:
                print(f"  [ERROR] Unexpected error in Neo4j query: {e}")
                return None

    def expand_with_graph(
        self,
        query: str,
        chunks: List[Dict],
        max_hops: int = 2,
        strategy: str = "auto"
    ) -> str:
        """
        Main entry point: Choose strategy based on query complexity

        Args:
            query: User query
            chunks: Retrieved chunks from hybrid search
            max_hops: Maximum graph traversal depth
            strategy: "local", "global", "hybrid", or "auto"

        Returns:
            Enriched context string for LLM
        """
        if strategy == "auto":
            # Determine strategy based on query
            strategy = self._detect_query_strategy(query, chunks)

        if strategy == "local":
            return self._local_entity_search(query, chunks, max_hops)
        elif strategy == "global":
            return self._global_semantic_search(query, chunks)
        elif strategy == "hybrid":
            local_ctx = self._local_entity_search(query, chunks, max_hops)
            global_ctx = self._global_semantic_search(query, chunks)
            return self._merge_contexts(local_ctx, global_ctx)
        else:
            # Fallback: basic expansion
            return self._local_entity_search(query, chunks, max_hops)

    def _detect_query_strategy(self, query: str, chunks: List[Dict]) -> str:
        """
        Detect best strategy based on query characteristics

        Local: Query mentions specific entities ("PPHN treatment", "ampicillin dose")
        Global: Broad queries ("neonatal complications", "NICU protocols")
        Hybrid: Complex queries ("differential diagnosis for respiratory distress")
        """
        query_lower = query.lower()

        # Check for specific medical terms (suggests local search)
        specific_terms = ["dose", "treatment for", "side effects of", "diagnosis of"]
        if any(term in query_lower for term in specific_terms):
            return "local"

        # Check for broad terms (suggests global search)
        broad_terms = ["overview", "types of", "all", "common", "main", "summary"]
        if any(term in query_lower for term in broad_terms):
            return "global"

        # Default: local search (most common for medical queries)
        return "local"

    def _local_entity_search(
        self,
        query: str,
        chunks: List[Dict],
        max_hops: int
    ) -> str:
        """
        Local Search Strategy (Entity-Focused)

        Steps:
        1. Extract entities from query + retrieved chunks
        2. Multi-hop traversal to find related entities
        3. Fetch related chunks via SIMILAR relationships
        4. Build enriched context

        Example:
        Query: "What treats PPHN?"
        → Find entity: PPHN (Condition)
        → Traverse: PPHN -[ADMINISTERED_TO]-> Drug
        → Traverse: PPHN -[SIMILAR]-> Related conditions
        → Return: Treatment drugs + related medical context
        """
        context_parts = []

        # Extract potential entity names from query and chunks
        entities = self._extract_entity_names(query, chunks)

        if not entities:
            return ""  # No entities found, skip KG enrichment

        print(f"  [KG LOCAL] Found {len(entities)} entities: {entities[:3]}...")

        # For each entity, traverse graph
        for entity_name in entities[:5]:  # Limit to top 5 entities
            entity_context = self._traverse_entity_neighborhood(
                entity_name,
                max_hops=max_hops
            )
            if entity_context:
                context_parts.append(entity_context)

        if not context_parts:
            return ""

        # Format as enriched context
        enriched_context = "\n\n".join(context_parts)
        return f"=== Knowledge Graph Context ===\n{enriched_context}\n=== End of KG Context ==="

    def _extract_entity_names(self, query: str, chunks: List[Dict]) -> List[str]:
        """
        Extract medical entities from query using LLM-based extraction

        This replaces regex-based extraction with a more robust LLM approach that can:
        - Identify medical conditions, diseases, symptoms
        - Recognize medications and treatments
        - Extract both abbreviations and full names (e.g., "GBS" and "Group B Streptococcus")
        - Understand medical context
        """
        if not self.llm:
            print("  [WARNING] No LLM available for entity extraction, falling back to empty list")
            return []

        # Build context from query and top retrieved chunk
        context = query
        if chunks:
            context += f"\n\nRelevant context: {chunks[0].get('text', '')[:300]}"

        extraction_prompt = f"""Extract ALL medical entities from the following text. Include:
- Diseases and conditions (e.g., "Group B Streptococcus", "respiratory distress", "sepsis")
- Symptoms (e.g., "tachypnea", "lethargy", "fever")
- Medications and treatments (e.g., "ampicillin", "gentamicin", "antibiotics")
- Medical abbreviations AND their full forms (e.g., both "GBS" and "Group B Streptococcus")
- Laboratory findings (e.g., "WBC", "CRP", "leukopenia")
- Procedures (e.g., "intubation", "mechanical ventilation")

Text:
{context}

Return ONLY a comma-separated list of medical entities. Include both abbreviations and full names when applicable.
Example: "GBS, Group B Streptococcus, sepsis, ampicillin, WBC, leukopenia"

Entities:"""

        try:
            response = self.llm.invoke(extraction_prompt)
            entity_text = response.content.strip()

            # Parse comma-separated entities
            entities = [e.strip() for e in entity_text.split(',') if e.strip()]

            print(f"  [LLM EXTRACTION] Found {len(entities)} entities: {entities[:5]}...")

            return entities[:15]  # Limit to 15 entities

        except Exception as e:
            print(f"  [ERROR] LLM entity extraction failed: {e}")
            return []

    def _search_entities_by_name(self, search_term: str) -> List[str]:
        """
        Search for entities in Neo4j that match search term
        Uses CONTAINS for partial matching (e.g., "pulmonary" matches "pulmonary hypertension")
        Uses driver.execute_query() for automatic retry
        """
        query = """
        MATCH (e)
        WHERE toLower(e.name) CONTAINS toLower($search_term)
        AND e.name IS NOT NULL
        AND NOT e:Chunk
        AND NOT e:Document
        RETURN DISTINCT e.name AS name
        LIMIT 5
        """

        try:
            records, summary, keys = self.neo4j.driver.execute_query(
                query,
                search_term=search_term,
                database_="neo4j"
            )
            return [record["name"] for record in records]
        except Exception as e:
            print(f"  [ERROR] Entity search failed: {e}")
            return []

    def _traverse_entity_neighborhood(
        self,
        entity_name: str,
        max_hops: int
    ) -> str:
        """
        Traverse entity neighborhood in graph
        Uses driver.execute_query() for automatic retry

        Query Pattern:
        1. Find entity node
        2. Traverse relationships (1-2 hops)
        3. Collect related entities and relationship types
        4. Format as context
        """
        # Multi-hop traversal query
        query = """
        MATCH (start)
        WHERE start.name = $entity_name

        // Get direct relationships (1 hop)
        OPTIONAL MATCH (start)-[r1]-(related1)
        WHERE NOT related1:Chunk AND NOT related1:Document

        // Get 2-hop relationships (if max_hops >= 2)
        OPTIONAL MATCH (start)-[r1]-(related1)-[r2]-(related2)
        WHERE NOT related1:Chunk AND NOT related1:Document
        AND NOT related2:Chunk AND NOT related2:Document
        AND $max_hops >= 2

        WITH start,
             collect(DISTINCT {
                 rel_type: type(r1),
                 target: related1.name,
                 target_type: labels(related1)[0]
             }) AS direct_rels,
             collect(DISTINCT {
                 rel_type: type(r2),
                 target: related2.name,
                 target_type: labels(related2)[0]
             }) AS indirect_rels

        RETURN
            start.name AS entity,
            labels(start)[0] AS entity_type,
            direct_rels,
            indirect_rels
        """

        try:
            records, summary, keys = self.neo4j.driver.execute_query(
                query,
                entity_name=entity_name,
                max_hops=max_hops,
                database_="neo4j"
            )

            if not records:
                return ""

            result = records[0]

            # Format context
            entity = result["entity"]
            entity_type = result["entity_type"]
            direct_rels = result["direct_rels"]
            indirect_rels = result["indirect_rels"] if max_hops >= 2 else []
        except Exception as e:
            print(f"  [ERROR] Entity traversal failed for '{entity_name}': {e}")
            return ""

            context_lines = [f"Entity: {entity} ({entity_type})"]

            # Format direct relationships
            if direct_rels:
                # Group by relationship type
                rel_groups = {}
                for rel in direct_rels:
                    if rel["target"]:  # Skip None values
                        rel_type = rel["rel_type"]
                        if rel_type not in rel_groups:
                            rel_groups[rel_type] = []
                        rel_groups[rel_type].append(f"{rel['target']} ({rel['target_type']})")

                for rel_type, targets in sorted(rel_groups.items()):
                    targets_str = ", ".join(targets[:5])  # Limit to 5 per relationship type
                    if len(targets) > 5:
                        targets_str += f" ... and {len(targets) - 5} more"
                    context_lines.append(f"  {rel_type}: {targets_str}")

            # Format indirect relationships (2-hop)
            if indirect_rels and max_hops >= 2:
                # Only show most relevant indirect relationships
                rel_groups = {}
                for rel in indirect_rels:
                    if rel["target"]:
                        rel_type = rel["rel_type"]
                        if rel_type not in rel_groups:
                            rel_groups[rel_type] = []
                        rel_groups[rel_type].append(rel["target"])

                if rel_groups:
                    context_lines.append("  Related (2-hop):")
                    for rel_type, targets in sorted(rel_groups.items()):
                        targets_str = ", ".join(targets[:3])  # Limit to 3
                        if len(targets) > 3:
                            targets_str += "..."
                        context_lines.append(f"    {rel_type}: {targets_str}")

            return "\n".join(context_lines)

    def _global_semantic_search(self, query: str, chunks: List[Dict]) -> str:
        """
        Global Search Strategy (Semantic Navigation)

        Uses SIMILAR relationships to find semantically related chunks

        Steps:
        1. Start from retrieved chunks
        2. Follow SIMILAR relationships to find related chunks
        3. Aggregate related content

        Example:
        Query: "What are neonatal complications?"
        → Retrieved chunks: [chunk_A, chunk_B]
        → Follow: chunk_A -[SIMILAR]-> chunk_C, chunk_D
        → Follow: chunk_B -[SIMILAR]-> chunk_E, chunk_F
        → Return: Aggregated semantic context from C, D, E, F
        """
        if not chunks:
            return ""

        # Get chunk IDs from retrieved chunks
        chunk_ids = [chunk.get("chunk_id") for chunk in chunks[:3]]  # Top 3 chunks

        context_parts = []

        for chunk_id in chunk_ids:
            similar_chunks = self._find_similar_chunks(chunk_id, limit=3)
            if similar_chunks:
                context_parts.append(
                    f"Related to '{chunk_id[:30]}...':\n" +
                    "\n".join([f"  - {c['text'][:150]}..." for c in similar_chunks])
                )

        if not context_parts:
            return ""

        return f"=== Semantic Context (SIMILAR chunks) ===\n" + "\n\n".join(context_parts) + "\n=== End ==="

    def _find_similar_chunks(self, chunk_id: str, limit: int = 3) -> List[Dict]:
        """
        Find chunks similar to given chunk via SIMILAR relationships
        Uses driver.execute_query() for automatic retry and connection management (Neo4j 5.x best practice)
        """
        query = """
        MATCH (start:Chunk {id: $chunk_id})-[s:SIMILAR]-(similar:Chunk)
        RETURN similar.text AS text, similar.id AS id
        ORDER BY s.score DESC
        LIMIT $limit
        """

        try:
            # Use driver.execute_query() - recommended Neo4j 5.x approach with automatic retry
            records, summary, keys = self.neo4j.driver.execute_query(
                query,
                chunk_id=chunk_id,
                limit=limit,
                database_="neo4j"  # Specify database explicitly
            )
            return [{"id": record["id"], "text": record["text"]} for record in records]
        except Exception as e:
            print(f"  [ERROR] Neo4j query failed after automatic retries: {e}")
            return []

    def _merge_contexts(self, local_context: str, global_context: str) -> str:
        """Merge local and global contexts"""
        contexts = []
        if local_context:
            contexts.append(local_context)
        if global_context:
            contexts.append(global_context)

        if not contexts:
            return ""

        return "\n\n" + "\n\n".join(contexts)

    def get_entity_context(self, entity_name: str) -> str:
        """
        Get rich context about a specific entity
        (Wrapper around old method for backward compatibility)
        """
        return self._traverse_entity_neighborhood(entity_name, max_hops=2)


# Backward compatibility: alias old class name
KGExpander = ModernKGExpander


if __name__ == "__main__":
    """Test modern KG expander"""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config import settings

    print("=== Testing Modern KG Expander ===\n")

    # Connect to Neo4j
    neo4j = Neo4jStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    # Initialize expander
    expander = ModernKGExpander(neo4j)

    # Test query
    test_query = "What is the treatment for PPHN?"
    print(f"Query: {test_query}\n")

    # Mock chunks (in real usage, these come from hybrid retrieval)
    mock_chunks = [
        {"chunk_id": "chunk_1", "text": "PPHN treatment includes inhaled nitric oxide..."},
        {"chunk_id": "chunk_2", "text": "Persistent pulmonary hypertension management..."}
    ]

    # Test local search
    print("[1] Local Search (Entity-Focused)")
    print("-" * 60)
    local_context = expander._local_entity_search(test_query, mock_chunks, max_hops=2)
    print(local_context)

    print("\n[2] Global Search (Semantic Navigation)")
    print("-" * 60)
    global_context = expander._global_semantic_search(test_query, mock_chunks)
    print(global_context)

    print("\n[3] Hybrid Search")
    print("-" * 60)
    hybrid_context = expander.expand_with_graph(test_query, mock_chunks, strategy="hybrid")
    print(hybrid_context)

    neo4j.close()
    print("\n[OK] Test complete!")
