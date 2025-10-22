"""
Re-index PDF documents using Jina AI Embeddings API
This ensures search queries and indexed documents use the same embedding space
"""
import os
import sys
from dotenv import load_dotenv
import requests
import numpy as np
import psycopg2
from typing import List, Dict, Any
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Configuration
JINA_API_KEY = os.getenv("JINA_API_KEY")
POSTGRES_URL = os.getenv("POSTGRES_URL")
TABLE_NAME = "medical_embeddings"
BATCH_SIZE = 50  # Process 50 chunks at a time

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


def main():
    print("=" * 80)
    print("RE-INDEXING WITH JINA AI EMBEDDINGS")
    print("=" * 80)
    print(f"Table: {TABLE_NAME}")
    print(f"Model: jina-embeddings-v3 (384D)")
    print(f"Task: retrieval.passage (optimized for documents)")
    print("=" * 80)

    # Connect to PostgreSQL
    print("\n[1/5] Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        print("✅ Connected")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # Get existing chunks (text + metadata only, not embeddings)
    print("\n[2/5] Fetching existing chunks...")
    try:
        cur.execute(f"""
            SELECT chunk_id, text, page_number, document_name
            FROM {TABLE_NAME}
            ORDER BY chunk_id
        """)
        chunks = cur.fetchall()
        total_chunks = len(chunks)
        print(f"✅ Found {total_chunks} chunks to re-index")

        if total_chunks == 0:
            print("\n⚠️  No chunks found. Please run the indexing script first.")
            print("   Use: python index_to_pgvector.py")
            sys.exit(0)
    except Exception as e:
        print(f"❌ Failed to fetch chunks: {e}")
        sys.exit(1)

    # Re-index in batches
    print(f"\n[3/5] Generating new embeddings with Jina AI (batch size: {BATCH_SIZE})...")
    updated_count = 0
    failed_count = 0

    for i in range(0, total_chunks, BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        try:
            # Extract texts and metadata
            chunk_ids = [row[0] for row in batch]
            texts = [row[1] for row in batch]

            # Generate embeddings via Jina AI API
            embeddings = encode_batch_jina(texts)

            # Update database
            for chunk_id, embedding in zip(chunk_ids, embeddings):
                embedding_list = embedding.tolist()
                cur.execute(f"""
                    UPDATE {TABLE_NAME}
                    SET embedding = %s::vector
                    WHERE chunk_id = %s
                """, (embedding_list, chunk_id))
                updated_count += 1

            conn.commit()
            print(f"   ✅ Batch {batch_num}/{total_batches} updated successfully")

            # Small delay to avoid rate limiting
            if i + BATCH_SIZE < total_chunks:
                time.sleep(0.5)

        except Exception as e:
            print(f"   ❌ Batch {batch_num} failed: {e}")
            failed_count += len(batch)
            conn.rollback()
            continue

    # Verify embeddings
    print(f"\n[4/5] Verifying embeddings...")
    try:
        cur.execute(f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME}
            WHERE embedding IS NOT NULL
        """)
        count_with_embeddings = cur.fetchone()[0]
        print(f"✅ {count_with_embeddings}/{total_chunks} chunks have embeddings")
    except Exception as e:
        print(f"⚠️  Verification failed: {e}")

    # Test search
    print(f"\n[5/5] Testing search with new embeddings...")
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
            WHERE embedding IS NOT NULL
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
    print("\n" + "=" * 80)
    print("RE-INDEXING COMPLETE")
    print("=" * 80)
    print(f"Total chunks: {total_chunks}")
    print(f"Successfully updated: {updated_count}")
    print(f"Failed: {failed_count}")
    print(f"Success rate: {(updated_count/total_chunks)*100:.1f}%")
    print("=" * 80)

    if updated_count > 0:
        print("\n✅ Your database now uses Jina AI embeddings!")
        print("   Both search and indexed documents use the same embedding space.")
        print("   You can now deploy to Render without OOM errors.")
    else:
        print("\n❌ Re-indexing failed. Please check the errors above.")


if __name__ == "__main__":
    main()
