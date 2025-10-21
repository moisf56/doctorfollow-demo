"""
Visualize RAG v3 LangGraph Workflow
Generates graph diagrams in multiple formats (ASCII, Mermaid, PNG)
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from rag_v3 import MedicalRAGv3


def main():
    """Generate RAG v3 workflow visualizations"""
    print("="*80)
    print("RAG v3 WORKFLOW VISUALIZATION")
    print("="*80)
    print()

    # Initialize RAG v3 (lightweight - just need the graph structure)
    print("[Loading] RAG v3 system...")
    rag = MedicalRAGv3()
    print("[OK] System loaded\n")

    # Generate visualizations
    print("="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)
    print()

    # 1. ASCII Visualization (terminal-friendly)
    print("[1] ASCII Visualization (terminal-friendly):")
    print()
    rag.visualize_graph(format="ascii")
    print()

    # 2. Mermaid Code (for mermaid.live)
    print("\n[2] Mermaid Code (copy to https://mermaid.live):")
    print()
    mermaid_file = Path(__file__).parent / "rag_v3_workflow.mmd"
    rag.visualize_graph(format="mermaid", output_path=str(mermaid_file))
    print()

    # 3. PNG Diagram (visual diagram)
    print("\n[3] PNG Diagram:")
    print()
    png_file = Path(__file__).parent / "rag_v3_workflow.png"
    rag.visualize_graph(format="png", output_path=str(png_file))
    print()

    # Summary
    print("="*80)
    print("VISUALIZATION COMPLETE")
    print("="*80)
    print()
    print("Generated files:")
    print(f"  1. Mermaid code: {mermaid_file}")
    print(f"  2. PNG diagram:  {png_file}")
    print()
    print("Workflow nodes:")
    print("  1. detect_language  - LLM-based language detection (tr/en)")
    print("  2. hybrid_retrieve  - BM25 + Semantic search with RRF fusion")
    print("  3. kg_enrich        - Knowledge graph context enrichment")
    print("  4. generate         - Language-aware LLM answer generation")
    print()
    print("Data stores:")
    print("  - OpenSearch (BM25 lexical search)")
    print("  - pgvector (Semantic similarity search)")
    print("  - Neo4j (Medical knowledge graph)")
    print()
    print("="*80)


if __name__ == "__main__":
    main()
