"""
Index Pediatrics PDF into Elasticsearch (Elastic Cloud)
Combines LangChain ingestion + Elasticsearch indexing
Updated to use environment variables for cloud deployment
"""
from pathlib import Path
import sys
import os   

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from pdf_ingestion import MedicalPDFIngestion
from opensearch_store import ElasticsearchStore


def index_pediatrics_pdf():
    """Index the Nelson Pediatrics PDF into Elasticsearch Cloud"""

    print("="*70)
    print("INDEXING PEDIATRICS PDF TO ELASTICSEARCH CLOUD")
    print("="*70)

    # Paths
    testing_dir = Path(__file__).parent.parent
    pdf_path = testing_dir / "data" / "Nelson-essentials-of-pediatrics-233-282.pdf"

    if not pdf_path.exists():
        print(f"\n[ERROR] PDF not found at: {pdf_path}")
        return False

    # Step 1: Ingest PDF with LangChain
    print(f"\n[STEP 1] Processing PDF with LangChain...")
    ingestion = MedicalPDFIngestion(chunk_size=400, chunk_overlap=100)
    chunks = ingestion.ingest_pdf(str(pdf_path))

    if not chunks:
        print("[ERROR] No chunks created")
        return False

    print(f"[OK] Created {len(chunks)} chunks")

    # Step 2: Connect to Elasticsearch (uses environment variables)
    print(f"\n[STEP 2] Connecting to Elasticsearch Cloud...")
    try:
        store = ElasticsearchStore()  # Now uses ES_URL, ES_API_KEY from environment
    except EnvironmentError as e:
        print(f"[ERROR] {e}")
        print("\n[INFO] Make sure these environment variables are set:")
        print("  - ES_URL=https://your-elastic-cloud.es.io:443")
        print("  - ES_API_KEY=your_api_key")
        print("  - ES_INDEX_NAME=doctor_follow_medical_chunks (optional)")
        return False

    # Step 3: Index chunks
    print(f"\n[STEP 3] Indexing {len(chunks)} chunks to Elasticsearch...")
    result = store.index_chunks(chunks)

    if result.get('error'):
        print(f"[ERROR] {result['error']}")
        return False

    print(f"[OK] Successfully indexed {result['indexed']} chunks")

    # Step 4: Verify
    print(f"\n[STEP 4] Verifying index...")
    stats = store.get_stats()
    if stats.get('exists'):
        print(f"  Total documents: {stats['total_documents']}")
        print(f"  Index size: {stats['index_size_bytes'] / 1024:.2f} KB")
        print(f"  Index name: {stats['index_name']}")
    else:
        print(f"[WARN] Could not retrieve stats: {stats.get('error', 'Unknown error')}")

    # Step 5: Test search
    print(f"\n[STEP 5] Testing search with sample queries...")

    test_queries = [
        "amoxicillin dosage",
        "otitis media treatment",
        "infant feeding",
    ]

    for query in test_queries:
        results = store.search(query, top_k=3)
        if results:
            print(f"\n  Query: '{query}'")
            print(f"  Top result score: {results[0].score:.3f}")
            print(f"  Top result page: {results[0].page_number}")
            print(f"  Preview: {results[0].text[:100]}...")
        else:
            print(f"\n  Query: '{query}'")
            print(f"  No results found")

    store.close()

    print(f"\n{'='*70}")
    print("INDEXING COMPLETE!")
    print("="*70)
    print(f"\n[INFO] You can now query the index with Turkish queries!")
    print(f"[INFO] Ready to build RAG v1 with LLM\n")

    return True


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    print("=== index Store  ===\n")
    
    load_dotenv()
    success = index_pediatrics_pdf()
    sys.exit(0 if success else 1)