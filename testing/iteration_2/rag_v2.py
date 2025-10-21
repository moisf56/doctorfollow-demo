"""
RAG v2: Hybrid Retrieval (BM25 + Semantic) + RRF Fusion + AWS Bedrock LLM
Iteration 2: Multi-retrieval agentic RAG with cross-lingual support

Architecture:
  Query → Hybrid Retrieval Node (BM25 + Semantic + RRF) → Generate Node (LLM) → Answer

Improvements over v1:
- ✅ BM25 (OpenSearch) for exact term matching
- ✅ Semantic search (pgvector) for cross-lingual retrieval
- ✅ RRF fusion for combining both signals
- ✅ Multilingual support (Turkish ↔ English)
"""
from typing import TypedDict, Annotated, Sequence, List
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from iteration_1.opensearch_store import OpenSearchStore
from pgvector_store import PgVectorStore
from rrf_fusion import RRFFusion


# ============================================
# State Definition (LangGraph Pattern)
# ============================================

class MedicalRAGState(TypedDict):
    """
    State for medical RAG system

    Following LangGraph pattern with messages accumulation
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    bm25_chunks: List[dict]  # BM25 results
    semantic_chunks: List[dict]  # Semantic results
    fused_chunks: List[dict]  # RRF fused results
    answer: str
    sources: List[dict]


# ============================================
# Hybrid RAG with RRF Fusion
# ============================================

class MedicalRAGv2:
    """
    Medical RAG v2 using LangGraph with Hybrid Retrieval

    Flow: Query → Hybrid Retrieve (BM25 + Semantic + RRF) → Generate → Answer

    Benefits:
    - BM25: Exact matching (drug names, medical terms)
    - Semantic: Cross-lingual, synonyms, concept matching
    - RRF: Best of both worlds
    """

    def __init__(
        self,
        opensearch_host: str = None,
        opensearch_port: int = None,
        postgres_url: str = None,
        top_k_bm25: int = 10,
        top_k_semantic: int = 10,
        top_k_final: int = 5,
        rrf_k: int = 60,
        model_id: str = None
    ):
        """
        Initialize RAG v2 with hybrid retrieval

        Args:
            opensearch_host: OpenSearch host (default from settings)
            opensearch_port: OpenSearch port (default from settings)
            postgres_url: PostgreSQL URL (default from settings)
            top_k_bm25: Number of BM25 results (default 10)
            top_k_semantic: Number of semantic results (default 10)
            top_k_final: Number of final fused results (default 5)
            rrf_k: RRF constant (default 60)
            model_id: AWS Bedrock model ID (default from settings)
        """
        # Use settings defaults if not provided
        opensearch_host = opensearch_host or settings.OPENSEARCH_HOST
        opensearch_port = opensearch_port or settings.OPENSEARCH_PORT
        postgres_url = postgres_url or settings.get_postgres_url()
        model_id = model_id or settings.BEDROCK_MODEL_ID

        # OpenSearch (BM25) retriever
        print("[Loading] OpenSearch (BM25)...")
        self.opensearch = OpenSearchStore(
            host=opensearch_host,
            port=opensearch_port,
            index_name=settings.OPENSEARCH_INDEX
        )

        # pgvector (Semantic) retriever
        print("[Loading] pgvector (Semantic)...")
        self.pgvector = PgVectorStore(
            connection_string=postgres_url,
            table_name=settings.PGVECTOR_TABLE,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION
        )

        # RRF Fusion
        self.rrf_fusion = RRFFusion(k=rrf_k)

        # Retrieval parameters
        self.top_k_bm25 = top_k_bm25
        self.top_k_semantic = top_k_semantic
        self.top_k_final = top_k_final

        # AWS Bedrock LLM
        print("[Loading] AWS Bedrock LLM...")
        try:
            self.llm = ChatBedrock(
                model_id=model_id,
                model_kwargs={
                    "temperature": 0.2,  # Low for medical accuracy
                    "max_tokens": 512
                }
            )
            print("[OK] AWS Bedrock LLM initialized")
        except Exception as e:
            print(f"[WARN] AWS Bedrock not available: {e}")
            print("[INFO] Will use mock LLM for testing")
            self.llm = None

        # Build LangGraph
        self.graph = self._build_graph()
        print("[OK] RAG v2 initialized")

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow

        Flow: hybrid_retrieve → generate → END
        """
        workflow = StateGraph(MedicalRAGState)

        # Add nodes
        workflow.add_node("hybrid_retrieve", self.hybrid_retrieve_node)
        workflow.add_node("generate", self.generate_node)

        # Define edges
        workflow.set_entry_point("hybrid_retrieve")
        workflow.add_edge("hybrid_retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def hybrid_retrieve_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """
        Hybrid Retrieval Node: BM25 + Semantic + RRF Fusion

        Args:
            state: Current state with query

        Returns:
            Updated state with fused chunks
        """
        query = state["query"]
        print(f"\n[HYBRID RETRIEVE] Query: {query}")

        # Step 1: BM25 retrieval (OpenSearch)
        print(f"  [BM25] Retrieving top {self.top_k_bm25} chunks...")
        bm25_results = self.opensearch.search(query, top_k=self.top_k_bm25)
        print(f"  [OK] BM25 retrieved {len(bm25_results)} chunks")

        # Step 2: Semantic retrieval (pgvector)
        print(f"  [Semantic] Retrieving top {self.top_k_semantic} chunks...")
        semantic_results = self.pgvector.search(query, top_k=self.top_k_semantic)
        print(f"  [OK] Semantic retrieved {len(semantic_results)} chunks")

        # Step 3: RRF Fusion
        print(f"  [RRF] Fusing results...")
        fused_results = self.rrf_fusion.fuse(
            bm25_results,
            semantic_results,
            top_k=self.top_k_final
        )
        print(f"  [OK] Fused to top {len(fused_results)} chunks")

        # Convert to dict format
        bm25_chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "page_number": r.page_number,
                "score": r.score,
                "source": "bm25"
            }
            for r in bm25_results
        ]

        semantic_chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "page_number": r.page_number,
                "score": r.score,
                "source": "semantic"
            }
            for r in semantic_results
        ]

        fused_chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "page_number": r.page_number,
                "rrf_score": r.rrf_score,
                "bm25_score": r.bm25_score,
                "semantic_score": r.semantic_score,
                "bm25_rank": r.bm25_rank,
                "semantic_rank": r.semantic_rank,
                "source": "hybrid"
            }
            for r in fused_results
        ]

        # Display top fused results
        print(f"\n  Top {min(3, len(fused_chunks))} Fused Results:")
        for i, chunk in enumerate(fused_chunks[:3], 1):
            print(f"    {i}. Page {chunk['page_number']}, RRF: {chunk['rrf_score']:.4f} "
                  f"(BM25 rank #{chunk['bm25_rank']}, Semantic rank #{chunk['semantic_rank']})")

        return {
            **state,
            "bm25_chunks": bm25_chunks,
            "semantic_chunks": semantic_chunks,
            "fused_chunks": fused_chunks
        }

    def generate_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """
        Generation Node: Create answer with citations using LLM

        Args:
            state: Current state with fused chunks

        Returns:
            Updated state with answer and sources
        """
        query = state["query"]
        chunks = state["fused_chunks"]

        print(f"\n[GENERATE] Creating answer with LLM...")

        # Build context from fused chunks
        context = ""
        for i, chunk in enumerate(chunks, 1):
            context += f"[Source {i}] (Page {chunk['page_number']})\n"
            context += f"{chunk['text']}\n\n"

        # Create prompt with citation instructions
        prompt = f"""You are a medical assistant for healthcare professionals. Answer the question based ONLY on the provided sources. Always cite sources using [Source N] format.

Sources:
{context}

Question: {query}

Instructions:
- Provide accurate medical information
- Cite sources for every claim using [Source N]
- If information is not in sources, say so
- Be concise and professional

Answer:"""

        # Generate with LLM
        if self.llm:
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                answer = response.content
                print(f"[OK] Answer generated ({len(answer)} chars)")
            except Exception as e:
                print(f"[ERROR] LLM generation failed: {e}")
                answer = f"Error generating answer: {e}"
        else:
            # Mock answer for testing
            answer = f"Based on the retrieved sources, this is a mock answer. (LLM not available)"

        return {
            **state,
            "answer": answer,
            "sources": chunks
        }

    def ask(self, query: str) -> dict:
        """
        Ask a question and get an answer

        Args:
            query: User question

        Returns:
            Dictionary with answer, sources, and metadata
        """
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "bm25_chunks": [],
            "semantic_chunks": [],
            "fused_chunks": [],
            "answer": "",
            "sources": []
        }

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        return {
            "query": query,
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "bm25_chunks": final_state["bm25_chunks"],
            "semantic_chunks": final_state["semantic_chunks"],
            "num_bm25": len(final_state["bm25_chunks"]),
            "num_semantic": len(final_state["semantic_chunks"]),
            "num_fused": len(final_state["fused_chunks"])
        }


if __name__ == "__main__":
    # Test RAG v2 with hybrid retrieval
    print("="*80)
    print("RAG v2 - Hybrid Retrieval Test")
    print("="*80)
    print()

    # Initialize
    rag = MedicalRAGv2()

    # Test queries (based on actual PDF content)
    test_queries = [
        "How is cardiac massage performed in newborns?",
        "Yenidoganlarda kalp masaji nasil yapilir?",  # Same in Turkish
    ]

    for i, query in enumerate(test_queries, 1):
        print("\n" + "="*80)
        print(f"TEST {i}: {query}")
        print("="*80)

        result = rag.ask(query)

        print(f"\n[RESULTS]")
        print(f"  BM25 chunks: {result['num_bm25']}")
        print(f"  Semantic chunks: {result['num_semantic']}")
        print(f"  Fused chunks: {result['num_fused']}")
        print(f"\n[ANSWER]")
        print(f"  {result['answer']}")
        print(f"\n[SOURCES] ({len(result['sources'])} sources)")
        for j, source in enumerate(result['sources'], 1):
            print(f"  {j}. Page {source['page_number']} - RRF: {source['rrf_score']:.4f}")

    print("\n" + "="*80)
    print("Test Complete!")
    print("="*80)
