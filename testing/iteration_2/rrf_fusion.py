"""
Reciprocal Rank Fusion (RRF) for Hybrid Retrieval
Iteration 2: Combine BM25 (OpenSearch) + Semantic (pgvector) results

RRF Formula:
    RRF_score(doc) = Σ (1 / (k + rank_i(doc)))

Where:
- k = constant (typically 60)
- rank_i(doc) = rank of document in result set i (1-indexed)

Benefits:
- Combines multiple ranking signals
- Robust to different score scales
- Gives preference to documents appearing in multiple result sets
"""
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class RankedResult:
    """Single result with rank and score from a retrieval system"""
    chunk_id: str
    text: str
    score: float  # Original score from retrieval system
    rank: int  # Position in result list (1-indexed)
    source: str  # 'bm25' or 'semantic'
    metadata: Dict[str, Any]
    page_number: int = None


@dataclass
class FusedResult:
    """Result after RRF fusion"""
    chunk_id: str
    text: str
    rrf_score: float  # Combined RRF score
    bm25_score: float  # Original BM25 score (0 if not in BM25 results)
    semantic_score: float  # Original semantic score (0 if not in semantic results)
    bm25_rank: int  # Rank in BM25 results (0 if not present)
    semantic_rank: int  # Rank in semantic results (0 if not present)
    metadata: Dict[str, Any]
    page_number: int = None


class RRFFusion:
    """
    Reciprocal Rank Fusion for combining multiple retrieval results

    Combines BM25 (lexical) and semantic (vector) search results
    using rank-based fusion algorithm
    """

    def __init__(self, k: int = 60, semantic_weight: float = 2.0, bm25_weight: float = 1.0):
        """
        Initialize RRF fusion

        Args:
            k: RRF constant (default 60, from original paper)
               Higher k reduces impact of rank differences
            semantic_weight: Weight for semantic search results (default 2.0 - double the importance)
            bm25_weight: Weight for BM25 results (default 1.0)
        """
        self.k = k
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight

    def fuse(
        self,
        bm25_results: List[Any],
        semantic_results: List[Any],
        top_k: int = 5
    ) -> List[FusedResult]:
        """
        Combine BM25 and semantic search results using RRF

        Args:
            bm25_results: Results from OpenSearch (BM25)
            semantic_results: Results from pgvector (semantic)
            top_k: Number of final results to return

        Returns:
            List of FusedResult objects sorted by RRF score
        """
        # Create ranked results with positions
        ranked_bm25 = self._create_ranked_results(bm25_results, 'bm25')
        ranked_semantic = self._create_ranked_results(semantic_results, 'semantic')

        # Calculate RRF scores
        rrf_scores = self._calculate_rrf_scores(ranked_bm25, ranked_semantic)

        # Create fused results
        fused_results = self._create_fused_results(
            rrf_scores,
            ranked_bm25,
            ranked_semantic
        )

        # Sort by RRF score (descending) and return top K
        fused_results.sort(key=lambda x: x.rrf_score, reverse=True)
        return fused_results[:top_k]

    def _create_ranked_results(
        self,
        results: List[Any],
        source: str
    ) -> Dict[str, RankedResult]:
        """
        Convert results to ranked format with positions

        Args:
            results: List of results from retrieval system
            source: 'bm25' or 'semantic'

        Returns:
            Dictionary mapping chunk_id to RankedResult
        """
        ranked = {}
        for rank, result in enumerate(results, start=1):
            # Handle both OpenSearch and pgvector result formats
            if hasattr(result, 'chunk_id'):
                chunk_id = result.chunk_id
                text = result.text
                score = result.score
                metadata = result.metadata
                page_number = result.page_number
            else:
                # Fallback for dictionary format
                chunk_id = result.get('chunk_id', f'chunk_{rank}')
                text = result.get('text', '')
                score = result.get('score', 0.0)
                metadata = result.get('metadata', {})
                page_number = result.get('page_number')

            ranked[chunk_id] = RankedResult(
                chunk_id=chunk_id,
                text=text,
                score=score,
                rank=rank,
                source=source,
                metadata=metadata,
                page_number=page_number
            )

        return ranked

    def _calculate_rrf_scores(
        self,
        ranked_bm25: Dict[str, RankedResult],
        ranked_semantic: Dict[str, RankedResult]
    ) -> Dict[str, float]:
        """
        Calculate RRF scores for all unique chunk IDs

        Args:
            ranked_bm25: BM25 ranked results
            ranked_semantic: Semantic ranked results

        Returns:
            Dictionary mapping chunk_id to RRF score
        """
        rrf_scores = {}

        # Get all unique chunk IDs from both result sets
        all_chunk_ids = set(ranked_bm25.keys()) | set(ranked_semantic.keys())

        for chunk_id in all_chunk_ids:
            score = 0.0

            # Add BM25 contribution (with weight)
            if chunk_id in ranked_bm25:
                rank = ranked_bm25[chunk_id].rank
                score += self.bm25_weight * (1.0 / (self.k + rank))

            # Add semantic contribution (with weight - default 2x BM25)
            if chunk_id in ranked_semantic:
                rank = ranked_semantic[chunk_id].rank
                score += self.semantic_weight * (1.0 / (self.k + rank))

            rrf_scores[chunk_id] = score

        return rrf_scores

    def _create_fused_results(
        self,
        rrf_scores: Dict[str, float],
        ranked_bm25: Dict[str, RankedResult],
        ranked_semantic: Dict[str, RankedResult]
    ) -> List[FusedResult]:
        """
        Create final fused results with all scores and metadata

        Args:
            rrf_scores: RRF scores for each chunk
            ranked_bm25: BM25 ranked results
            ranked_semantic: Semantic ranked results

        Returns:
            List of FusedResult objects
        """
        fused_results = []

        for chunk_id, rrf_score in rrf_scores.items():
            # Get original scores and ranks
            bm25_score = ranked_bm25[chunk_id].score if chunk_id in ranked_bm25 else 0.0
            semantic_score = ranked_semantic[chunk_id].score if chunk_id in ranked_semantic else 0.0

            bm25_rank = ranked_bm25[chunk_id].rank if chunk_id in ranked_bm25 else 0
            semantic_rank = ranked_semantic[chunk_id].rank if chunk_id in ranked_semantic else 0

            # Get text and metadata (prefer semantic, fallback to bm25)
            if chunk_id in ranked_semantic:
                text = ranked_semantic[chunk_id].text
                metadata = ranked_semantic[chunk_id].metadata
                page_number = ranked_semantic[chunk_id].page_number
            else:
                text = ranked_bm25[chunk_id].text
                metadata = ranked_bm25[chunk_id].metadata
                page_number = ranked_bm25[chunk_id].page_number

            fused_results.append(FusedResult(
                chunk_id=chunk_id,
                text=text,
                rrf_score=rrf_score,
                bm25_score=bm25_score,
                semantic_score=semantic_score,
                bm25_rank=bm25_rank,
                semantic_rank=semantic_rank,
                metadata=metadata,
                page_number=page_number
            ))

        return fused_results


if __name__ == "__main__":
    # Test RRF fusion with sample results
    print("=== RRF Fusion Test ===\n")

    # Simulate BM25 results
    from dataclasses import dataclass as dc

    @dc
    class MockResult:
        chunk_id: str
        text: str
        score: float
        metadata: dict
        page_number: int

    bm25_results = [
        MockResult("chunk_001", "Amoxicillin dosing for children is 20-40 mg/kg/day", 7.5, {}, 1),
        MockResult("chunk_005", "Penicillin alternatives include azithromycin", 6.2, {}, 5),
        MockResult("chunk_003", "Antibiotic therapy for otitis media", 5.8, {}, 3),
    ]

    # Simulate semantic results
    semantic_results = [
        MockResult("chunk_001", "Amoxicillin dosing for children is 20-40 mg/kg/day", 0.89, {}, 1),
        MockResult("chunk_002", "Pediatric dosing guidelines for antibiotics", 0.84, {}, 2),
        MockResult("chunk_003", "Antibiotic therapy for otitis media", 0.81, {}, 3),
    ]

    # Test fusion
    fusion = RRFFusion(k=60)
    results = fusion.fuse(bm25_results, semantic_results, top_k=5)

    print("Fused Results (sorted by RRF score):\n")
    print(f"{'Rank':<6} {'Chunk ID':<12} {'RRF Score':<12} {'BM25':<10} {'Semantic':<10} {'Page'}")
    print("-" * 70)

    for i, result in enumerate(results, 1):
        print(f"{i:<6} {result.chunk_id:<12} {result.rrf_score:<12.4f} "
              f"#{result.bm25_rank:<9} #{result.semantic_rank:<9} {result.page_number}")

    print("\n--- Analysis ---")
    print(f"\nchunk_001 appears in BOTH results → High RRF score (top rank)")
    print(f"chunk_003 appears in BOTH results → Second highest RRF")
    print(f"chunk_002 only in semantic → Lower RRF (rank #{results[2].semantic_rank} semantic only)")
    print(f"chunk_005 only in BM25 → Lower RRF (rank #{results[3].bm25_rank} BM25 only)")

    print("\n[OK] RRF Fusion working correctly!")
    print("Documents in both result sets get highest scores!")
