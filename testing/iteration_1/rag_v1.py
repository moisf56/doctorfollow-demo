"""
RAG v1: OpenSearch BM25 + AWS Bedrock LLM with LangGraph
Iteration 1: Basic agentic RAG following LangGraph patterns

Architecture (simplified from mermaid diagram for Iteration 1):
  Query → Retrieval Node (OpenSearch BM25) → Generate Node (LLM) → Answer

Future iterations will add:
- Iter 2: pgvector + RRF fusion
- Iter 3: Knowledge graph
- Iter 4: Full agentic routing
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
sys.path.append(str(Path(__file__).parent))
from opensearch_store import OpenSearchStore


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
    retrieved_chunks: List[dict]
    answer: str
    sources: List[dict]


# ============================================
# Nodes (LangGraph Pattern)
# ============================================

class MedicalRAGv1:
    """
    Medical RAG v1 using LangGraph

    Simple flow: Query → Retrieve (BM25) → Generate → Answer
    """

    def __init__(
        self,
        opensearch_host: str = "localhost",
        opensearch_port: int = 9200,
        top_k: int = 5,
        model_id: str = "us.meta.llama4-scout-17b-instruct-v1:0"
    ):
        """
        Initialize RAG v1

        Args:
            opensearch_host: OpenSearch host
            opensearch_port: OpenSearch port
            top_k: Number of chunks to retrieve
            model_id: AWS Bedrock model ID
        """
        # OpenSearch retriever
        self.opensearch = OpenSearchStore(
            host=opensearch_host,
            port=opensearch_port,
            index_name="medical_chunks"
        )
        self.top_k = top_k

        # AWS Bedrock LLM
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

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow

        Flow: retrieve → generate → END
        """
        workflow = StateGraph(MedicalRAGState)

        # Add nodes
        workflow.add_node("retrieve", self.retrieve_node)
        workflow.add_node("generate", self.generate_node)

        # Define edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def retrieve_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """
        Retrieval Node: BM25 search in OpenSearch

        Args:
            state: Current state with query

        Returns:
            Updated state with retrieved chunks
        """
        query = state["query"]
        print(f"\n[RETRIEVE] Searching for: {query}")

        # OpenSearch BM25 retrieval
        results = self.opensearch.search(query, top_k=self.top_k)

        # Convert to dict format
        chunks = [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "page_number": r.page_number,
                "score": r.score
            }
            for r in results
        ]

        print(f"[OK] Retrieved {len(chunks)} chunks")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"  {i}. Page {chunk['page_number']}, Score: {chunk['score']:.2f}")

        return {
            **state,
            "retrieved_chunks": chunks
        }

    def generate_node(self, state: MedicalRAGState) -> MedicalRAGState:
        """
        Generation Node: Create answer with citations using LLM

        Args:
            state: Current state with retrieved chunks

        Returns:
            Updated state with answer and sources
        """
        query = state["query"]
        chunks = state["retrieved_chunks"]

        print(f"\n[GENERATE] Creating answer with LLM...")

        # Build context from retrieved chunks
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
            except Exception as e:
                print(f"[ERROR] LLM invocation failed: {e}")
                answer = self._mock_answer(query, chunks)
        else:
            answer = self._mock_answer(query, chunks)

        print(f"[OK] Generated answer ({len(answer)} chars)")

        # Extract sources for citation
        sources = [
            {
                "source_id": i,
                "page": chunk["page_number"],
                "text": chunk["text"][:200] + "..."
            }
            for i, chunk in enumerate(chunks, 1)
        ]

        return {
            **state,
            "answer": answer,
            "sources": sources
        }

    def _mock_answer(self, query: str, chunks: List[dict]) -> str:
        """Mock answer when LLM not available"""
        return f"Based on the retrieved information:\n\n{chunks[0]['text'][:300]}... [Source 1]\n\n(Mock answer - AWS Bedrock not configured)"

    def ask(self, query: str) -> dict:
        """
        Main interface: Ask a question

        Args:
            query: User question (Turkish or English)

        Returns:
            Dictionary with answer, sources, and metadata
        """
        # Initialize state
        initial_state = {
            "messages": [],
            "query": query,
            "retrieved_chunks": [],
            "answer": "",
            "sources": []
        }

        # Run through LangGraph
        final_state = self.graph.invoke(initial_state)

        return {
            "query": query,
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "num_chunks_retrieved": len(final_state["retrieved_chunks"]),
            "retrieval_scores": [c["score"] for c in final_state["retrieved_chunks"]]
        }


# ============================================
# CLI Interface
# ============================================

def main():
    """Test RAG v1 with sample queries"""
    print("="*70)
    print("MEDICAL RAG v1 - ITERATION 1 TEST")
    print("OpenSearch BM25 + AWS Bedrock LLM with LangGraph")
    print("="*70)

    # Initialize
    rag = MedicalRAGv1()

    # Test queries (English and Turkish)
    test_queries = [
        "What is the dosage of amoxicillin for children?",
        "Çocuklarda amoksisilin dozu nedir?",  # Turkish
        "How is otitis media treated?",
    ]

    for query in test_queries:
        print(f"\n\n{'='*70}")
        print(f"QUERY: {query}")
        print("="*70)

        result = rag.ask(query)

        print(f"\nANSWER:")
        print(result["answer"])

        print(f"\n\nSOURCES:")
        for source in result["sources"][:3]:
            print(f"  [Source {source['source_id']}] Page {source['page']}")
            print(f"    {source['text']}")

        print(f"\n\nMETADATA:")
        print(f"  Chunks retrieved: {result['num_chunks_retrieved']}")
        print(f"  BM25 scores: {[f'{s:.2f}' for s in result['retrieval_scores'][:3]]}")

    print(f"\n\n{'='*70}")
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
