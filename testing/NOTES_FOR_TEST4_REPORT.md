# Notes for TEST4 REPORT - Semantic vs RRF Analysis

## Key Insight: Semantic-Only vs RRF Trade-offs

### For Turkish Queries: Semantic-Only Performs Better
- Turkish has NO lexical overlap with English medical terms
- BM25 ALWAYS fails for pure Turkish queries (retrieves irrelevant content)
- RRF includes 2-3/5 results from failed BM25 → adds noise
- **Recommendation**: Use semantic-only for Turkish to avoid dilution

### For English Queries: RRF Hybrid Performs Better
- Both BM25 and semantic work well
- Consensus from both systems → higher confidence
- RRF prioritizes chunks appearing in BOTH result sets
- **Recommendation**: Use RRF for English queries

### Quantitative Evidence:

**Turkish "Cardiac Massage" Query:**
```
Semantic-only: 0.813 avg similarity ✅ (5/5 correct)
BM25-only: 3.74 avg score ❌ (0/5 correct, wrong content)
RRF Hybrid: Mixed (3 correct from semantic, 2 wrong from BM25)
```

**English "Patent Ductus Arteriosus" Query:**
```
Semantic-only: 0.853 avg similarity ✅
BM25-only: 13.25 avg score ✅
RRF Hybrid: 5/5 results from BOTH systems ⭐ (consensus!)
```

### Future Optimization: Adaptive Retrieval

```python
if detect_language(query) == "turkish":
    # Semantic-only (BM25 will fail)
    results = pgvector.search(query)
elif detect_language(query) == "english":
    # Hybrid RRF (consensus from both)
    results = rrf_fusion(bm25, semantic)
```

**Decision for Now**: Stick with RRF for consistency across iterations, document this insight for future optimization.

---

**Date**: 2025-10-18
**Status**: To be included in TEST4_REPORT.md
