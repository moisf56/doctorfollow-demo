"""
Index PDF documents using Jina AI Embeddings API
This script chunks PDFs and generates embeddings via Jina AI (no local model needed)
"""
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import requests
import numpy as np
import psycopg2
from typing import List
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "iteration_1"))

load_dotenv()

# Import PDF processing separately (avoid config validation issues)
try:
    from iteration_1.pdf_ingestion import MedicalPDFIngestion
except ImportError:
    print("❌ Could not import PDF ingestion. Make sure iteration_1 is available.")
    sys.exit(1)

# Configuration
JINA_API_KEY = os.getenv("JINA_API_KEY")
POSTGRES_URL = os.getenv("POSTGRES_URL")
TABLE_NAME = "medical_embeddings"
BATCH_SIZE = 50  # Process 50 chunks at a time
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))

if not JINA_API_KEY:
    print("❌ Error: JINA_API_KEY not found in .env")
    print("Get a free API key from: https://jina.ai/embeddings/")
    sys.exit(1)

if not POSTGRES_URL:
    print("❌ Error: POSTGRES_URL not found in .env")
    sys.exit(1)


def encode_batch_jina(texts: List[str], retry: int = 3) -> List[np.ndarray]:
    """
    Encode a batch of texts using Jina AI Embeddings API

    Args:
        texts: List of texts to encode
        retry: Number of retry attempts

    Returns:
        List of embedding vectors
    """
    API_URL = "https://api.jina.ai/v1/embeddings"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}"
    }

    # Use jina-embeddings-v3 with 384D and retrieval.passage task for documents
    data = {
        "input": texts,
        "model": "jina-embeddings-v3",
        "dimensions": 384,
        "task": "retrieval.passage"  # Optimized for indexing documents
    }

    for attempt in range(retry):
        try:
            response = requests.post(API_URL, headers=headers, json=data)

            if response.status_code == 200:
                result = response.json()
                embeddings = [np.array(item["embedding"]) for item in result["data"]]
                return embeddings

            elif response.status_code == 503:
                wait_time = 2 ** attempt
                print(f"   [INFO] API temporarily unavailable, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            elif response.status_code == 429:
                wait_time = 5 * (attempt + 1)
                print(f"   [WARN] Rate limit exceeded, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            else:
                raise Exception(f"Jina AI API error: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            if attempt == retry - 1:
                raise Exception(f"Failed to connect to Jina AI API: {e}")
            print(f"   [WARN] API request failed (attempt {attempt + 1}/{retry}), retrying...")
            time.sleep(1)

    raise Exception("Failed to get embeddings from Jina AI API after retries")


def setup_database(conn):
    """Create pgvector extension and table if not exists"""
    cur = conn.cursor()

    # Create extension
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Create table
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            chunk_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            embedding vector(384),
            page_number INTEGER,
            document_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create index for similarity search
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx
        ON {TABLE_NAME}
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)

    conn.commit()
    cur.close()


def main():
    """
    Main ingestion pipeline:
    1. Load and chunk PDF
    2. Generate embeddings via Jina AI API
    3. Index to pgvector
    """
    print("="*80)
    print("PDF INDEXING WITH JINA AI EMBEDDINGS")
    print("="*80)
    print(f"Model: jina-embeddings-v3 (384D)")
    print(f"Task: retrieval.passage (optimized for documents)")
    print(f"Batch size: {BATCH_SIZE}")
    print("="*80)

    # Step 1: Locate PDF
    pdf_path = DATA_DIR / "Nelson-essentials-of-pediatrics-233-282.pdf"

    if not pdf_path.exists():
        print(f"\n❌ PDF not found at: {pdf_path}")
        print(f"   Please ensure the PDF is in: {DATA_DIR}/")
        sys.exit(1)

    print(f"\n[1/5] Found PDF: {pdf_path.name}")

    # Step 2: Initialize PDF ingestion
    print("\n[2/5] Initializing PDF ingestion...")
    ingestion = MedicalPDFIngestion(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    print("✅ PDF ingestion initialized")

    # Step 3: Process PDF and chunk
    print("\n[3/5] Processing and chunking PDF...")
    chunks = ingestion.ingest_pdf(str(pdf_path))
    print(f"✅ Generated {len(chunks)} chunks")

    if len(chunks) == 0:
        print("❌ No chunks generated. Please check the PDF.")
        sys.exit(1)

    # Step 4: Connect to database
    print("\n[4/5] Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        print("✅ Connected")

        print("   Setting up database...")
        setup_database(conn)
        print("✅ Database setup complete")
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        sys.exit(1)

    # Step 5: Index chunks with Jina AI embeddings
    print(f"\n[5/5] Indexing {len(chunks)} chunks with Jina AI...")
    indexed_count = 0
    failed_count = 0
    cur = conn.cursor()

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        try:
            # Extract texts
            texts = [chunk["text"] for chunk in batch]

            # Generate embeddings via Jina AI API
            embeddings = encode_batch_jina(texts)

            # Insert into database
            for chunk, embedding in zip(batch, embeddings):
                embedding_list = embedding.tolist()
                cur.execute(f"""
                    INSERT INTO {TABLE_NAME} (chunk_id, text, embedding, page_number, document_name)
                    VALUES (%s, %s, %s::vector, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE
                    SET text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        page_number = EXCLUDED.page_number,
                        document_name = EXCLUDED.document_name
                """, (
                    chunk["chunk_id"],
                    chunk["text"],
                    embedding_list,
                    chunk["page_number"],
                    chunk.get("document_name", pdf_path.name)
                ))
                indexed_count += 1

            conn.commit()
            print(f"   ✅ Batch {batch_num}/{total_batches} indexed successfully")

            # Small delay to avoid rate limiting
            if i + BATCH_SIZE < len(chunks):
                time.sleep(0.5)

        except Exception as e:
            print(f"   ❌ Batch {batch_num} failed: {e}")
            failed_count += len(batch)
            conn.rollback()
            continue

    # Verify
    print("\n[Verification] Checking indexed chunks...")
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total_in_db = cur.fetchone()[0]
    print(f"✅ Total chunks in database: {total_in_db}")

    # Test search
    print("\n[Test] Testing search...")
    try:
        test_query = "What is RDS treatment?"
        print(f"   Query: '{test_query}'")

        # Get query embedding
        query_embeddings = encode_batch_jina([test_query])
        query_embedding = query_embeddings[0].tolist()

        # Search
        cur.execute(f"""
            SELECT chunk_id, text, page_number,
                   1 - (embedding <=> %s::vector) as similarity
            FROM {TABLE_NAME}
            ORDER BY embedding <=> %s::vector
            LIMIT 3
        """, (query_embedding, query_embedding))

        results = cur.fetchall()
        print(f"   ✅ Found {len(results)} results")

        if len(results) > 0:
            print(f"\n   Top result:")
            print(f"   - Chunk ID: {results[0][0]}")
            print(f"   - Page: {results[0][2]}")
            print(f"   - Similarity: {results[0][3]:.4f}")
            print(f"   - Text: {results[0][1][:150]}...")
    except Exception as e:
        print(f"   ❌ Search test failed: {e}")

    # Close connection
    cur.close()
    conn.close()

    # Summary
    print("\n" + "="*80)
    print("INDEXING COMPLETE")
    print("="*80)
    print(f"Total chunks: {len(chunks)}")
    print(f"Successfully indexed: {indexed_count}")
    print(f"Failed: {failed_count}")
    print(f"Success rate: {(indexed_count/len(chunks))*100:.1f}%")
    print("="*80)

    if indexed_count > 0:
        print("\n✅ Your database is ready!")
        print("   Embeddings generated with: jina-embeddings-v3 (384D)")
        print("   Search queries will use the same model (via API)")
        print("   You can now deploy to Render without OOM errors!")
    else:
        print("\n❌ Indexing failed. Please check the errors above.")


if __name__ == "__main__":
    main()
