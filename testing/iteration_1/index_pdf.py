"""
Index Pediatrics PDF into OpenSearch
Combines LangChain ingestion + OpenSearch indexing
"""
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from pdf_ingestion import MedicalPDFIngestion
from opensearch_store import OpenSearchStore


def index_pediatrics_pdf():
    """Index the Nelson Pediatrics PDF into OpenSearch"""

    print("="*70)
    print("INDEXING PEDIATRICS PDF TO OPENSEARCH")
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

    # Step 2: Connect to OpenSearch
    print(f"\n[STEP 2] Connecting to OpenSearch...")
    store = OpenSearchStore(
        host="localhost",
        port=9200,
        index_name="medical_chunks"
    )

    # Step 3: Index chunks
    print(f"\n[STEP 3] Indexing {len(chunks)} chunks to OpenSearch...")
    result = store.index_chunks(chunks)

    if result.get('error'):
        print(f"[ERROR] {result['error']}")
        return False

    print(f"[OK] Successfully indexed {result['indexed']} chunks")

    # Step 4: Verify
    print(f"\n[STEP 4] Verifying index...")
    stats = store.get_stats()
    print(f"  Total documents: {stats['total_documents']}")
    print(f"  Index size: {stats['index_size_bytes'] / 1024:.2f} KB")

    # Step 5: Test search
    print(f"\n[STEP 5] Testing search with sample queries...")

    test_queries = [
        "amoxicillin dosage",
        "otitis media treatment",
        "infant feeding",
    ]

    for query in test_queries:
        results = store.search(query, top_k=3)
        print(f"\n  Query: '{query}'")
        print(f"  Top result score: {results[0].score:.3f}")
        print(f"  Top result page: {results[0].page_number}")
        print(f"  Preview: {results[0].text[:100]}...")

    store.close()

    print(f"\n{'='*70}")
    print("INDEXING COMPLETE!")
    print("="*70)
    print(f"\n[INFO] You can now query the index with Turkish queries!")
    print(f"[INFO] Ready to build RAG v1 with AWS Bedrock LLM\n")

    return True


if __name__ == "__main__":
    success = index_pediatrics_pdf()
    sys.exit(0 if success else 1)
