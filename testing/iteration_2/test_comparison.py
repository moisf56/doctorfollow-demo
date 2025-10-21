"""
Comparison Test: Semantic-Only vs Hybrid (BM25 + Semantic + RRF)
Shows the value of hybrid retrieval with RRF fusion
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))
sys.path.append(str(Path(__file__).parent))

from config import settings
from pgvector_store import PgVectorStore
from iteration_1.opensearch_store import OpenSearchStore
from rrf_fusion import RRFFusion


def test_comparison():
    """
    Compare semantic-only vs hybrid retrieval
    """
    print("="*80)
    print("COMPARISON TEST: Semantic-Only vs Hybrid Retrieval")
    print("="*80)
    print()

    # Initialize stores
    print("[Loading] Initializing retrieval systems...")

    # Semantic (pgvector)
    pgvector = PgVectorStore(
        connection_string=settings.get_postgres_url(),
        table_name=settings.PGVECTOR_TABLE,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=settings.EMBEDDING_DIMENSION
    )

    # BM25 (OpenSearch)
    opensearch = OpenSearchStore(
        host=settings.OPENSEARCH_HOST,
        port=settings.OPENSEARCH_PORT,
        index_name=settings.OPENSEARCH_INDEX
    )

    # RRF Fusion
    rrf = RRFFusion(k=settings.RRF_K)

    print("[OK] All systems loaded\n")

    # Test queries (mix of English and Turkish)
    test_queries = [
        {
            "english": "How is cardiac massage performed in newborns?",
            "turkish": "Yenidoganlarda kalp masaji nasil yapilir?",
            "topic": "Neonatal cardiac massage"
        },
        {
            "english": "What is patent ductus arteriosus?",
            "turkish": "Patent duktus arteriosus nedir?",
            "topic": "Ductus arteriosus"
        },
        {
            "english": "Treatment of apnea in premature infants",
            "turkish": "Premature bebeklerde apne tedavisi",
            "topic": "Apnea of prematurity"
        }
    ]

    for i, test in enumerate(test_queries, 1):
        print("="*80)
        print(f"TEST {i}/{len(test_queries)}: {test['topic']}")
        print("="*80)

        # Test both languages
        for lang, query in [("English", test['english']), ("Turkish", test['turkish'])]:
            print(f"\n{lang} Query: {query}")
            print("-"*80)

            # 1. Semantic-only retrieval
            print("\n[1] SEMANTIC ONLY (pgvector):")
            semantic_results = pgvector.search(query, top_k=5)

            print("  Top 5 Results:")
            for j, result in enumerate(semantic_results, 1):
                print(f"    {j}. Page {result.page_number:2d} | Similarity: {result.score:.3f}")
                print(f"       {result.text[:100]}...")

            avg_semantic = sum(r.score for r in semantic_results) / len(semantic_results)
            print(f"  Average Similarity: {avg_semantic:.3f}")

            # 2. BM25 retrieval
            print("\n[2] BM25 ONLY (OpenSearch):")
            bm25_results = opensearch.search(query, top_k=5)

            print("  Top 5 Results:")
            for j, result in enumerate(bm25_results, 1):
                print(f"    {j}. Page {result.page_number:2d} | BM25 Score: {result.score:.2f}")
                print(f"       {result.text[:100]}...")

            avg_bm25 = sum(r.score for r in bm25_results) / len(bm25_results) if bm25_results else 0
            print(f"  Average BM25 Score: {avg_bm25:.2f}")

            # 3. Hybrid with RRF fusion
            print("\n[3] HYBRID (BM25 + Semantic + RRF):")
            bm25_for_rrf = opensearch.search(query, top_k=10)
            semantic_for_rrf = pgvector.search(query, top_k=10)
            fused_results = rrf.fuse(bm25_for_rrf, semantic_for_rrf, top_k=5)

            print("  Top 5 Fused Results:")
            for j, result in enumerate(fused_results, 1):
                bm25_rank_str = f"#{result.bm25_rank}" if result.bm25_rank > 0 else "---"
                sem_rank_str = f"#{result.semantic_rank}" if result.semantic_rank > 0 else "---"
                print(f"    {j}. Page {result.page_number:2d} | RRF: {result.rrf_score:.4f} "
                      f"(BM25: {bm25_rank_str}, Sem: {sem_rank_str})")
                print(f"       {result.text[:100]}...")

            avg_rrf = sum(r.rrf_score for r in fused_results) / len(fused_results)
            print(f"  Average RRF Score: {avg_rrf:.4f}")

            # 4. Analysis
            print("\n[ANALYSIS]:")

            # Count overlaps
            semantic_ids = {r.chunk_id for r in semantic_results}
            bm25_ids = {r.chunk_id for r in bm25_results}
            fused_ids = {r.chunk_id for r in fused_results}

            overlap_bm25_semantic = len(semantic_ids & bm25_ids)
            in_both = len([r for r in fused_results if r.bm25_rank > 0 and r.semantic_rank > 0])
            from_bm25_only = len([r for r in fused_results if r.bm25_rank > 0 and r.semantic_rank == 0])
            from_semantic_only = len([r for r in fused_results if r.bm25_rank == 0 and r.semantic_rank > 0])

            print(f"  Overlap (BM25 & Semantic): {overlap_bm25_semantic}/5")
            print(f"  Fused results from:")
            print(f"    - Both BM25 & Semantic: {in_both}")
            print(f"    - BM25 only: {from_bm25_only}")
            print(f"    - Semantic only: {from_semantic_only}")

            if in_both > 0:
                print(f"  Verdict: RRF prioritized chunks appearing in BOTH results!")
            elif from_semantic_only > from_bm25_only:
                print(f"  Verdict: RRF favored semantic results (better for this query)")
            elif from_bm25_only > from_semantic_only:
                print(f"  Verdict: RRF favored BM25 results (better for this query)")
            else:
                print(f"  Verdict: RRF balanced both approaches equally")

            print()

    # Cleanup
    pgvector.close()
    opensearch.close()

    print("="*80)
    print("COMPARISON TEST COMPLETE")
    print("="*80)
    print("\nKey Insights:")
    print("- Semantic: Best for cross-lingual queries (Turkish -> English)")
    print("- BM25: Best for exact term matching (drug names, medical terms)")
    print("- Hybrid (RRF): Combines strengths of both approaches")
    print("- RRF prioritizes chunks appearing in multiple result sets")


if __name__ == "__main__":
    test_comparison()
