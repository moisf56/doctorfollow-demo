"""
Index Embeddings to pgvector
Iteration 2: Generate multilingual embeddings and index to PostgreSQL

Reuses chunking logic from iteration_1 for consistency
Same 894 chunks, but now with semantic embeddings
"""
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "iteration_1"))

from config import settings
from iteration_1.pdf_ingestion import MedicalPDFIngestion
from pgvector_store import PgVectorStore


def main():
    """
    Main ingestion pipeline:
    1. Load and chunk PDF (using iteration_1 logic)
    2. Generate multilingual embeddings
    3. Index to pgvector
    """
    print("="*70)
    print("ITERATION 2: Embedding Ingestion to pgvector")
    print("="*70)
    print()

    # Step 1: Locate PDF
    pdf_path = settings.DATA_DIR / "Nelson-essentials-of-pediatrics-233-282.pdf"

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found at: {pdf_path}")
        print(f"[INFO] Please ensure the PDF is in: {settings.DATA_DIR}/")
        return

    print(f"[OK] Found PDF: {pdf_path.name}")
    print()

    # Step 2: Initialize components
    print("[Loading] Initializing PDF ingestion (same as iteration_1)...")
    ingestion = MedicalPDFIngestion(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    print("[OK] PDF ingestion initialized")
    print()

    print("[Loading] Initializing pgvector store with multilingual embeddings...")
    pgvector_store = PgVectorStore(
        connection_string=settings.get_postgres_url(),
        table_name=settings.PGVECTOR_TABLE,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=settings.EMBEDDING_DIMENSION
    )
    print()

    # Step 3: Process PDF (reuse iteration_1 chunking)
    print("="*70)
    print("STEP 1: Chunking PDF")
    print("="*70)
    chunks = ingestion.ingest_pdf(str(pdf_path))

    print()
    print(f"[OK] Created {len(chunks)} chunks")
    print(f"[INFO] Chunk size: {settings.CHUNK_SIZE} chars")
    print(f"[INFO] Chunk overlap: {settings.CHUNK_OVERLAP} chars")
    print()

    # Show sample
    print("--- Sample Chunk ---")
    sample = chunks[0]
    print(f"Chunk ID: {sample['chunk_id']}")
    print(f"Page: {sample['page_number']}")
    print(f"Text length: {len(sample['text'])} chars")
    print(f"Text preview: {sample['text'][:200]}...")
    print()

    # Step 4: Index to pgvector with embeddings
    print("="*70)
    print("STEP 2: Generating Embeddings & Indexing to pgvector")
    print("="*70)
    print(f"[INFO] Embedding model: {settings.EMBEDDING_MODEL}")
    print(f"[INFO] Embedding dimension: {settings.EMBEDDING_DIMENSION}")
    print(f"[INFO] This will take a few minutes (generating {len(chunks)} embeddings)...")
    print()

    result = pgvector_store.index_chunks(chunks, batch_size=32)

    print()
    print("="*70)
    print("Indexing Results")
    print("="*70)
    for key, value in result.items():
        print(f"{key}: {value}")

    # Step 5: Verify with stats
    print()
    print("="*70)
    print("pgvector Table Stats")
    print("="*70)
    stats = pgvector_store.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    # Step 6: Test cross-lingual search
    print()
    print("="*70)
    print("STEP 3: Testing Cross-Lingual Search")
    print("="*70)

    # Test with a Turkish query from your test set
    test_query = "Çocuklarda amoksisilin dozu nedir?"
    print(f"\nTest Query (Turkish): {test_query}")
    print(f"Translation: What is the amoxicillin dose for children?")
    print()

    results = pgvector_store.search(test_query, top_k=5)

    print("Top 5 Results:")
    print("-" * 70)
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Similarity: {result.score:.3f} | Page: {result.page_number}")
        print(f"   {result.text[:150]}...")

    # Compare with English query
    print()
    print("="*70)
    print("Comparison: English vs Turkish Query")
    print("="*70)

    test_query_en = "What is the amoxicillin dose for children?"
    print(f"\nTest Query (English): {test_query_en}")
    print()

    results_en = pgvector_store.search(test_query_en, top_k=5)

    print("Top 5 Results:")
    print("-" * 70)
    for i, result in enumerate(results_en, 1):
        print(f"\n{i}. Similarity: {result.score:.3f} | Page: {result.page_number}")
        print(f"   {result.text[:150]}...")

    # Cleanup
    pgvector_store.close()

    print()
    print("="*70)
    print("SUCCESS - Iteration 2 Indexing Complete!")
    print("="*70)
    print()
    print("Next Steps:")
    print("1. ✅ pgvector indexed with multilingual embeddings")
    print("2. ⏭️  Create rrf_fusion.py for hybrid retrieval")
    print("3. ⏭️  Create rag_v2.py combining BM25 + semantic search")
    print("4. ⏭️  Test and measure improvement vs iteration_1")
    print()


if __name__ == "__main__":
    main()
