"""
RAG v3: Hybrid Retrieval + Knowledge Graph Enrichment + LLM
Iteration 3: Graph-enhanced RAG with medical knowledge graph

Architecture:
  Query → Hybrid Retrieval (BM25 + Semantic + RRF)
       → KG Enrichment (expand with graph context)
       → Generate (LLM with enriched context)
       → Answer

Improvements over v2:
- ✅ All v2 features (BM25 + Semantic + RRF)
- ✅ Knowledge graph context enrichment
- ✅ Multi-hop reasoning via graph traversal
- ✅ Structured medical knowledge (diseases, drugs, symptoms, relationships)
"""
from typing import TypedDict, Annotated, Sequence, List
from pathlib import Path
import sys
import os
from dotenv import load_dotenv
import re

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directories for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent.parent / "iteration_2"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import ElasticsearchStore
from iteration_2.pgvector_store import PgVectorStore
from iteration_2.rrf_fusion import RRFFusion
from neo4j_store import Neo4jStore
from kg_expander import KGExpander


# ============================================
# State Definition (LangGraph Pattern)
# ============================================

class MedicalRAGState(TypedDict):
    """State for medical RAG system with KG enrichment"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    query_language: str  # Detected language code (e.g., 'tr', 'en')
    query_complexity: str  # 'simple_fact' or 'complex_reasoning'
    bm25_chunks: List[dict]
    semantic_chunks: List[dict]
    fused_chunks: List[dict]
    kg_context: str  # Knowledge graph context
    answer: str
    sources: List[dict]


# ============================================
# RAG v3 with Knowledge Graph
# ============================================

class MedicalRAGv3:
    """
    Medical RAG v3: Hybrid Retrieval + Knowledge Graph Enrichment

    Flow:
      Query → Hybrid Retrieve → KG Expand → Generate → Answer
    """

    def __init__(
        self,
        postgres_url: str = None,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        neo4j_password: str = None,
        top_k_bm25: int = 10,
        top_k_semantic: int = 10,
        top_k_final: int = 3,  # Changed from 5 to 3 for more focused results
        rrf_k: int = 60,
        model_id: str = None
    ):
        """
        Initialize RAG v3 with hybrid retrieval + KG

        Args:
            postgres_url: PostgreSQL URL
            neo4j_uri: Neo4j URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            top_k_bm25: Number of BM25 results
            top_k_semantic: Number of semantic results
            top_k_final: Number of final fused results
            rrf_k: RRF constant
            model_id: AWS Bedrock model ID
        """
        # Use settings defaults if not provided
        postgres_url = postgres_url or settings.get_postgres_url()
        neo4j_uri = neo4j_uri or settings.NEO4J_URI
        neo4j_user = neo4j_user or settings.NEO4J_USER
        neo4j_password = neo4j_password or settings.NEO4J_PASSWORD
        model_id = model_id or settings.BEDROCK_MODEL_ID

        # Initialize retrieval systems
        print("[Loading] ElasticSearch (BM25)...")
        # ElasticsearchStore now uses environment variables (ES_URL, ES_API_KEY, ES_INDEX_NAME)
        self.opensearch = ElasticsearchStore()

        print("[Loading] pgvector (Semantic)...")
        self.pgvector = PgVectorStore(
            connection_string=postgres_url,
            table_name=settings.PGVECTOR_TABLE,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            load_model=True  # Load model locally (multilingual-e5-small is small: ~280MB total)
        )

        print("[Loading] Neo4j (Knowledge Graph)...")
        self.neo4j = Neo4jStore(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )

        # Initialize RRF fusion with weighted semantic similarity (2x more important than BM25)
        self.rrf_fusion = RRFFusion(k=rrf_k, semantic_weight=2.0, bm25_weight=1.0)
        self.kg_expander = KGExpander(self.neo4j)

        # Retrieval parameters
        self.top_k_bm25 = top_k_bm25
        self.top_k_semantic = top_k_semantic
        self.top_k_final = top_k_final

        # Initialize LLM based on provider
        llm_provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

        if llm_provider == "openai":
            print("[Loading] OpenAI LLM...")
            try:
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    temperature=0.2,
                    max_tokens=512,
                    api_key=os.getenv("OPENAI_API_KEY")
                )
                print(f"[OK] OpenAI LLM initialized (model: {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})")
            except Exception as e:
                print(f"[ERROR] OpenAI initialization failed: {e}")
                self.llm = None
        else:
            # AWS Bedrock (default)
            print("[Loading] AWS Bedrock LLM...")
            try:
                self.llm = ChatBedrock(
                    model_id=model_id,
                    model_kwargs={
                        "temperature": 0.2,
                        "max_tokens": 512
                    }
                )
                print("[OK] AWS Bedrock LLM initialized")
            except Exception as e:
                print(f"[WARN] AWS Bedrock not available: {e}")
                self.llm = None

        # Build LangGraph
        self.graph = self._build_graph()
        print("[OK] RAG v3 initialized")

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow with conditional KG enrichment (language detected in API)"""
        workflow = StateGraph(MedicalRAGState)

        # Add nodes (language detection removed - done in API)
        workflow.add_node("hybrid_retrieve", self.hybrid_retrieve_node)
        workflow.add_node("kg_enrich", self.kg_enrich_node)
        workflow.add_node("generate", self.generate_node)

        # Conditional routing function
        def should_use_kg(state: MedicalRAGState) -> str:
            """Route to KG enrichment only for complex queries"""
            complexity = state.get("query_complexity", "simple")
            if complexity == "complex":
                return "kg_enrich"
            else:
                return "generate"

        # Define edges
        workflow.set_entry_point("hybrid_retrieve")  # Start directly with retrieval

        # Conditional edge: simple → generate, complex → kg_enrich
        workflow.add_conditional_edges(
            "hybrid_retrieve",
            should_use_kg,
            {
                "kg_enrich": "kg_enrich",
                "generate": "generate"
            }
        )

        workflow.add_edge("kg_enrich", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def hybrid_retrieve_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """Hybrid retrieval node (same as v2)"""
        query = state["query"]
        complexity = state.get("query_complexity", "simple")

        try:
            print(f"\n[HYBRID RETRIEVE] Query: {query} (complexity: {complexity})")
        except UnicodeEncodeError:
            print(f"\n[HYBRID RETRIEVE] Query: [Unicode text] (complexity: {complexity})")

        # BM25 retrieval
        print(f"  [BM25] Retrieving top {self.top_k_bm25}...")
        bm25_results = self.opensearch.search(query, top_k=self.top_k_bm25)
        print(f"  [OK] BM25 retrieved {len(bm25_results)} chunks")

        # Semantic retrieval
        print(f"  [Semantic] Retrieving top {self.top_k_semantic}...")
        semantic_results = self.pgvector.search(query, top_k=self.top_k_semantic)
        print(f"  [OK] Semantic retrieved {len(semantic_results)} chunks")

        # RRF Fusion
        print(f"  [RRF] Fusing results...")
        fused_results = self.rrf_fusion.fuse(
            bm25_results,
            semantic_results,
            top_k=self.top_k_final
        )
        print(f"  [OK] Fused to top {len(fused_results)} chunks")

        # Convert to dict format
        bm25_chunks = [{"chunk_id": r.chunk_id, "text": r.text, "page_number": r.page_number, "score": r.score} for r in bm25_results]
        semantic_chunks = [{"chunk_id": r.chunk_id, "text": r.text, "page_number": r.page_number, "score": r.score} for r in semantic_results]
        fused_chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "page_number": r.page_number,
                "rrf_score": r.rrf_score,
                "bm25_score": r.bm25_score,
                "semantic_score": r.semantic_score
            }
            for r in fused_results
        ]

        return {
            **state,
            "bm25_chunks": bm25_chunks,
            "semantic_chunks": semantic_chunks,
            "fused_chunks": fused_chunks
        }

    def kg_enrich_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """Knowledge graph enrichment node"""
        query = state["query"]
        chunks = state["fused_chunks"]

        try:
            print(f"\n[KG ENRICH] Expanding with knowledge graph...")
        except UnicodeEncodeError:
            print("\n[KG ENRICH] Expanding with knowledge graph...")

        # Expand with KG context
        kg_context = self.kg_expander.expand_with_graph(query, chunks, max_hops=2)

        if kg_context:
            print(f"  [OK] Added knowledge graph context ({len(kg_context)} chars)")
        else:
            print(f"  [INFO] No additional KG context found")

        return {
            **state,
            "kg_context": kg_context
        }

    def generate_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """Generation node with Chain-of-Thought reasoning for complex queries"""
        query = state["query"]
        chunks = state["fused_chunks"]
        kg_context = state.get("kg_context", "")
        query_language = state.get("query_language", "en")
        query_complexity = state.get("query_complexity", "simple_fact")

        try:
            print(f"\n[GENERATE] Creating answer (language: {query_language}, complexity: {query_complexity})...")
        except UnicodeEncodeError:
            print(f"\n[GENERATE] Creating answer...")

        # Build context from chunks
        chunks_context = ""
        for i, chunk in enumerate(chunks, 1):
            chunks_context += f"[Source {i}] (Page {chunk['page_number']})\n"
            chunks_context += f"{chunk['text']}\n\n"

        # Language-specific instructions
        language_instruction = ""
        if query_language == 'tr':
            language_instruction = """
CRITICAL: Respond in TURKISH (Türkçe). The user's question is in Turkish.
- Provide your ENTIRE answer in Turkish
- Use proper Turkish medical terminology
- Translate medical terms appropriately while keeping Latin names in parentheses where needed
- Maintain professional medical language in Turkish
- Keep citation format [Source N] as is
"""
        elif query_language == 'en':
            language_instruction = """
CRITICAL: Respond in ENGLISH.
- Provide your entire answer in English
- Use proper medical terminology
- Maintain professional medical language
"""
        else:
            language_instruction = "Respond in the same language as the user's question."

        # Chain-of-Thought reasoning for complex queries
        if query_complexity == 'complex_reasoning':
            cot_instruction = """
IMPORTANT - CHAIN-OF-THOUGHT REASONING:
This query requires deep medical reasoning. Follow these steps:

1. SYMPTOM/PROBLEM ANALYSIS: Identify key symptoms, findings, or clinical problems mentioned
2. DIFFERENTIAL CONSIDERATIONS: List relevant differential diagnoses or treatment options based on sources
3. CLINICAL REASONING: Analyze each possibility against the available evidence from sources
4. KNOWLEDGE INTEGRATION: Integrate information from multiple sources and knowledge graph context
5. RECOMMENDATION: Provide evidence-based recommendations with clear reasoning

Structure your response with explicit thinking:
<reasoning>
Step 1 - Symptom Analysis: [Identify key clinical features]
Step 2 - Differential: [List possible diagnoses/treatments from sources]
Step 3 - Analysis: [Evaluate each option with evidence]
Step 4 - Integration: [Synthesize information]
Step 5 - Conclusion: [Final recommendation with reasoning]
</reasoning>

<answer>
[Provide your detailed medical answer with inline citations [Source 1], [Source 2], etc.]
</answer>
"""
        else:
            # Simple fact - direct answer
            cot_instruction = """
Provide a clear, concise answer to this factual question.
"""

        # Create prompt
        prompt = f"""You are a medical assistant for healthcare professionals. Answer the question based on the provided sources and knowledge graph context.

{language_instruction}

{cot_instruction}

Sources from PDF:
{chunks_context}

{kg_context if kg_context else ""}

Question: {query}

Instructions:
- Provide accurate medical information
- Cite sources inline using [Source N] format within your answer
- Use knowledge graph context to enrich your answer
- If information is not in sources, say so
- Be thorough and professional
- IMPORTANT: Structure your response in TWO sections:
  1. First section: Your detailed answer (with <reasoning> if complex query)
  2. Second section: A "References:" section listing all sources used

Format your response EXACTLY like this:

{"<reasoning>[Your step-by-step thinking]</reasoning>" if query_complexity == 'complex_reasoning' else ""}

<answer>
[Your detailed medical answer here with inline citations [Source 1], [Source 2], etc.]
</answer>

---
References:
[Source 1] - Page X: Brief description of what this source covered
[Source 2] - Page Y: Brief description of what this source covered
[etc.]

Final Answer:"""

        # Generate with LLM - adjust max_tokens for complex reasoning
        if self.llm:
            try:
                # Adjust max_tokens based on complexity
                max_tokens = 1500 if query_complexity == 'complex_reasoning' else 512

                # Create LLM with adjusted max_tokens based on provider
                llm_provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

                if llm_provider == "openai":
                    from langchain_openai import ChatOpenAI
                    llm_for_generation = ChatOpenAI(
                        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                        temperature=0.2,
                        max_tokens=max_tokens,
                        api_key=os.getenv("OPENAI_API_KEY")
                    )
                else:
                    # Bedrock
                    from langchain_aws import ChatBedrock
                    llm_for_generation = ChatBedrock(
                        model_id=os.getenv("BEDROCK_MODEL_ID"),
                        model_kwargs={
                            "temperature": 0.2,
                            "max_tokens": max_tokens
                        },
                        region_name=os.getenv("AWS_REGION", "us-east-1")
                    )

                response = llm_for_generation.invoke([HumanMessage(content=prompt)])
                answer = response.content
                print(f"[OK] Answer generated ({len(answer)} chars, max_tokens={max_tokens})")
            except Exception as e:
                print(f"[ERROR] LLM generation failed: {e}")
                answer = f"Error: {e}"
        else:
            answer = "Mock answer (LLM not available)"

        return {
            **state,
            "answer": answer,
            "sources": chunks
        }

    def ask(self, query: str, language: str = "en", complexity: str = "simple") -> dict:
        """
        Ask a question and get an answer with optional Chain-of-Thought reasoning

        Args:
            query: The medical question
            language: 'en' or 'tr' - passed from API classification
            complexity: 'simple' or 'complex' - determines if KG enrichment is used
        """
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "query_language": language,  # Passed from API classification
            "query_complexity": complexity,  # Passed from API classification
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
            "kg_context": final_state["kg_context"],
            "num_sources": len(final_state["sources"])
        }

    def visualize_graph(self, output_path: str = None, format: str = "png") -> None:
        """
        Visualize the LangGraph workflow

        Args:
            output_path: Path to save visualization (optional)
            format: Output format - 'png', 'mermaid', or 'ascii'
        """
        try:
            if format == "png":
                # Generate PNG using Mermaid
                png_data = self.graph.get_graph().draw_mermaid_png()

                if output_path:
                    # Save to file
                    with open(output_path, 'wb') as f:
                        f.write(png_data)
                    print(f"[OK] Graph visualization saved to: {output_path}")
                else:
                    # Try to display in Jupyter/IPython
                    try:
                        from IPython.display import Image, display
                        display(Image(png_data))
                    except ImportError:
                        # Save to default location if not in Jupyter
                        default_path = "rag_v3_graph.png"
                        with open(default_path, 'wb') as f:
                            f.write(png_data)
                        print(f"[OK] Graph visualization saved to: {default_path}")
                        print(f"[INFO] Not in Jupyter environment - saved as PNG file")

            elif format == "mermaid":
                # Generate Mermaid code
                mermaid_code = self.graph.get_graph().draw_mermaid()

                if output_path:
                    with open(output_path, 'w') as f:
                        f.write(mermaid_code)
                    print(f"[OK] Mermaid code saved to: {output_path}")
                else:
                    print("\n[MERMAID CODE]")
                    print("-" * 80)
                    print(mermaid_code)
                    print("-" * 80)
                    print("\nCopy this code to https://mermaid.live to visualize")

            elif format == "ascii":
                # Generate ASCII representation
                ascii_graph = self.graph.get_graph().draw_ascii()
                print("\n[ASCII GRAPH]")
                print("-" * 80)
                print(ascii_graph)
                print("-" * 80)

            else:
                print(f"[ERROR] Unknown format: {format}. Use 'png', 'mermaid', or 'ascii'")

        except Exception as e:
            print(f"[ERROR] Failed to generate graph visualization: {e}")
            print(f"[INFO] Make sure you have the required dependencies installed")
            print(f"       For PNG: pip install pygraphviz or pyppeteer")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("="*80)
    print("RAG v3 - Hybrid Retrieval + Knowledge Graph Test")
    print("="*80)
    print()

    # Initialize
    rag = MedicalRAGv3()

    # Visualize graph workflow
    print("\n" + "="*80)
    print("VISUALIZING LANGGRAPH WORKFLOW")
    print("="*80)

    # Generate ASCII visualization
    print("\n[1] ASCII Visualization:")
    rag.visualize_graph(format="ascii")

    # Generate Mermaid code
    print("\n[2] Mermaid Code:")
    rag.visualize_graph(format="mermaid", output_path="rag_v3_graph.mmd")

    # Generate PNG
    print("\n[3] PNG Diagram:")
    rag.visualize_graph(format="png", output_path="rag_v3_graph.png")

    # Test query
    query = "What is the treatment for PPHN in newborns?"

    print("\n" + "="*80)
    print(f"QUERY: {query}")
    print("="*80)

    result = rag.ask(query)

    print(f"\n[ANSWER]")
    print(result["answer"])

    print(f"\n[SOURCES] ({result['num_sources']} sources)")
    for i, source in enumerate(result['sources'], 1):
        print(f"  {i}. Page {source['page_number']} - RRF: {source['rrf_score']:.4f}")

    if result['kg_context']:
        print(f"\n[KNOWLEDGE GRAPH CONTEXT]")
        print(result['kg_context'][:500] + "..." if len(result['kg_context']) > 500 else result['kg_context'])

    print("\n" + "="*80)
    print("Test Complete!")
    print("="*80)