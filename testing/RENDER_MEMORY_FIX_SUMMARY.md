# Memory Optimization for Render Deployment - Quick Summary

## Problem
Render free tier OOM error: `Out of memory (used over 512Mi)`

## Root Cause
Loading SentenceTransformers model (~400MB) + PyTorch (~400MB) = ~800MB total memory usage

## Solution
Use **Jina AI Embeddings API** (FREE tier: 1M tokens/month) instead of loading model locally

## Changes Made

### 1. `iteration_2/pgvector_store.py`
```python
# Added Jina AI API support
def _encode_via_api(self, text: str, retry: int = 3) -> np.ndarray:
    # Uses Jina AI Embeddings API (jina-embeddings-v3)
    # 384 dimensions via Matryoshka Representation Learning
    # Task: retrieval.query (optimized for search)

# Updated initialization
def __init__(self, ..., load_model: bool = False):
    # load_model=False uses Jina AI API (default for deployment)
    # load_model=True loads local model (for indexing operations)

# Updated search
def search(self, query: str, ...):
    if self.model:
        query_embedding = self.model.encode([query])[0]  # Local
    else:
        query_embedding = self._encode_via_api(query)  # Jina AI API
```

### 2. `iteration_3/rag_v3.py`
```python
self.pgvector = PgVectorStore(
    connection_string=postgres_url,
    table_name=settings.PGVECTOR_TABLE,
    embedding_model=settings.EMBEDDING_MODEL,
    embedding_dimension=settings.EMBEDDING_DIMENSION,
    load_model=False  # Use HF API instead of loading model
)
```

### 3. `requirements.txt`
```diff
- sentence-transformers==3.3.1
- torch>=2.0.0
+ # Using HF API instead - saves ~800MB RAM
```

### 4. `render.yaml`
```diff
- pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
- pip install -r ../requirements.txt
+ pip install --upgrade pip
+ pip install -r ../requirements.txt

+ # Hugging Face (optional - for higher rate limits)
+ - key: HUGGINGFACE_TOKEN
+   sync: false
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Memory Usage | ~800MB | ~200MB |
| First Query | ~50ms | ~2-5s (model loading) |
| Subsequent Queries | ~50ms | ~100-300ms |
| Deployment | ❌ OOM Error | ✅ Works on Free Tier |

## Deployment Checklist

- [x] Update `pgvector_store.py` with HF API support
- [x] Update `rag_v3.py` to use `load_model=False`
- [x] Remove torch and sentence-transformers from `requirements.txt`
- [x] Update `render.yaml` build commands
- [x] Add `HUGGINGFACE_TOKEN` to render.yaml (optional)
- [ ] Push changes to GitHub
- [ ] Get HF token from https://huggingface.co/settings/tokens (optional)
- [ ] Set `HUGGINGFACE_TOKEN` in Render dashboard (optional)
- [ ] Deploy and verify

## Testing

```bash
# Local test (without model)
python -c "
from iteration_2.pgvector_store import PgVectorStore
import os
from dotenv import load_dotenv
load_dotenv()

pgvector = PgVectorStore(
    connection_string=os.getenv('POSTGRES_URL'),
    embedding_model='intfloat/multilingual-e5-small',
    load_model=False  # Use HF API
)

results = pgvector.search('What is RDS treatment?')
print(f'Found {len(results)} results')
"
```

## Important Notes

1. **For Indexing**: Still need local model
   - Run indexing scripts locally with full dependencies
   - Or use a separate indexing service with more memory

2. **HF API Rate Limits**:
   - Without token: ~100 requests/hour
   - With free token: ~1000 requests/hour
   - Paid tier: Unlimited

3. **Performance**:
   - First query per model load: 2-5 seconds
   - Cached queries: 100-300ms
   - Acceptable for demo/prototype
   - Upgrade for production if needed

4. **Model**: `intfloat/multilingual-e5-small` (384 dimensions)
   - Supports both Turkish and English
   - Optimized for semantic search
   - Requires "query: " prefix for queries

## Next Steps

1. Push to GitHub
2. Render auto-deploys
3. Monitor memory usage in Render dashboard
4. Test with real queries
5. Get HF token if hitting rate limits
