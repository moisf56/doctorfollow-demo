"""
PostgreSQL + pgvector Store for DoctorFollow
Iteration 2: Semantic search with pgvector
Auto-creates vector extension on connection
"""
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
from dataclasses import dataclass
import numpy as np
import os
import time
import requests

# Optional: Load sentence-transformers if available (for backward compatibility)
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("[INFO] sentence-transformers not installed, will use Hugging Face API")

@dataclass
class SearchResult:
    """Single search result from pgvector"""
    chunk_id: str
    text: str
    score: float  # Cosine similarity (higher = better, 0-1 range)
    metadata: Dict[str, Any]
    page_number: Optional[int] = None
    paragraph_id: Optional[str] = None


class PgVectorStore:
    """
    PostgreSQL + pgvector client for semantic search
    
    Features:
    - Semantic similarity search using embeddings
    - Cosine similarity scoring
    - Efficient vector indexing with HNSW
    - Auto-creates vector extension
    """
    
    def __init__(
        self,
        connection_string: str,
        table_name: str = "medical_embeddings",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_dimension: int = 384,
        load_model: bool = False  # NEW: Don't load model by default (use HF API)
    ):
        """
        Initialize pgvector store

        Args:
            connection_string: PostgreSQL connection string
            table_name: Name of the table to store embeddings
            embedding_model: Sentence transformer model name
            embedding_dimension: Dimension of embeddings (384 for MiniLM-L6-v2)
            load_model: If True, load model locally. If False, use HF API (saves memory!)
        """
        self.table_name = table_name
        self.embedding_dimension = embedding_dimension
        self.embedding_model = embedding_model

        # Connect to PostgreSQL
        self.conn = psycopg2.connect(connection_string)
        self.conn.autocommit = False

        # Create vector extension if it doesn't exist
        self._create_vector_extension()

        # Create table with vector column
        self._create_table()

        # Optionally load embedding model locally (memory intensive!)
        self.model = None
        if load_model and HAS_SENTENCE_TRANSFORMERS:
            print(f"[Loading] Embedding model locally: {embedding_model}...")
            self.model = SentenceTransformer(embedding_model)
            print(f"[OK] Embedding model loaded (dimension: {embedding_dimension})")
        else:
            print(f"[INFO] Using Hugging Face API for embeddings (saves ~400MB RAM)")
            print(f"[INFO] Model: {embedding_model}")

    def _encode_via_hf_api(self, text: str, retry: int = 3) -> np.ndarray:
        """
        Use Hugging Face Inference API for embeddings

        Args:
            text: Text to encode
            retry: Number of retry attempts

        Returns:
            Embedding vector as numpy array
        """
        # For multilingual-e5-small, add "query: " prefix for search queries
        # (This improves retrieval performance per model documentation)
        if not text.startswith("query: "):
            text = f"query: {text}"

        API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.embedding_model}"
        headers = {}

        # Use API key if available (higher rate limits)
        hf_token = os.getenv("HUGGINGFACE_TOKEN")
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"

        for attempt in range(retry):
            try:
                response = requests.post(API_URL, headers=headers, json={"inputs": text})

                if response.status_code == 200:
                    # API returns array of embeddings, take first one
                    embedding = np.array(response.json()[0])
                    return embedding

                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    wait_time = 2 ** attempt
                    print(f"[INFO] Model loading, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                else:
                    raise Exception(f"HF API error: {response.status_code} - {response.text}")

            except requests.exceptions.RequestException as e:
                if attempt == retry - 1:
                    raise Exception(f"Failed to connect to HF API: {e}")
                print(f"[WARN] API request failed (attempt {attempt + 1}/{retry}), retrying...")
                time.sleep(1)

        raise Exception("Failed to get embedding from HF API after retries")

    def _create_vector_extension(self):
        """Create pgvector extension if it doesn't exist"""
        with self.conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                self.conn.commit()
                print("[OK] pgvector extension ready")
            except Exception as e:
                self.conn.rollback()
                print(f"[WARN] Could not create vector extension: {e}")
                print("[INFO] If this fails, you may need to enable it manually:")
                print("       Run: CREATE EXTENSION vector; in your PostgreSQL database")
                raise
    
    def _create_table(self):
        """Create table with vector column and indexes"""
        with self.conn.cursor() as cur:
            # Create table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    chunk_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding vector({self.embedding_dimension}),
                    page_number INTEGER,
                    paragraph_id TEXT,
                    document_name TEXT,
                    chunk_index INTEGER,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create HNSW index for fast similarity search
            # Only create if table has data and index doesn't exist
            cur.execute(f"""
                SELECT COUNT(*) FROM {self.table_name}
            """)
            count = cur.fetchone()[0]
            
            if count > 0:
                # Check if index exists
                cur.execute(f"""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = '{self.table_name}' 
                    AND indexname = '{self.table_name}_embedding_idx'
                """)
                
                if not cur.fetchone():
                    print(f"[Creating] HNSW index on {count} vectors...")
                    cur.execute(f"""
                        CREATE INDEX {self.table_name}_embedding_idx 
                        ON {self.table_name} 
                        USING hnsw (embedding vector_cosine_ops)
                    """)
                    print("[OK] HNSW index created")
            
            self.conn.commit()
            print(f"[OK] Table '{self.table_name}' ready")
    
    def index_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Index chunks with embeddings

        Args:
            chunks: List of chunk dictionaries with text and metadata

        Returns:
            Statistics about indexing
        """
        if not chunks:
            return {"error": "No chunks provided"}

        # Check if model is loaded (required for bulk indexing)
        if not self.model:
            raise ValueError(
                "Cannot index chunks without local model loaded. "
                "Initialize with load_model=True for indexing operations. "
                "HF API is only suitable for single query encoding (search operations)."
            )

        # Generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        print(f"[Embedding] Generating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Prepare data for insertion
        values = []
        for chunk, embedding in zip(chunks, embeddings):
            values.append((
                chunk.get("chunk_id", f"chunk_{len(values)}"),
                chunk["text"],
                embedding.tolist(),  # Convert numpy array to list
                chunk.get("page_number"),
                chunk.get("paragraph_id"),
                chunk.get("document_name"),
                chunk.get("chunk_index"),
                psycopg2.extras.Json(chunk.get("metadata", {}))
            ))
        
        # Bulk insert
        with self.conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {self.table_name} 
                (chunk_id, text, embedding, page_number, paragraph_id, 
                 document_name, chunk_index, metadata)
                VALUES %s
                ON CONFLICT (chunk_id) DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    page_number = EXCLUDED.page_number,
                    paragraph_id = EXCLUDED.paragraph_id,
                    document_name = EXCLUDED.document_name,
                    chunk_index = EXCLUDED.chunk_index,
                    metadata = EXCLUDED.metadata
                """,
                values
            )
            self.conn.commit()
        
        print(f"[OK] Indexed {len(chunks)} chunks with embeddings")
        
        # Create/update index if we now have enough data
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cur.fetchone()[0]
            
            if count >= 10:  # Only create index if we have enough data
                # Check if index exists
                cur.execute(f"""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = '{self.table_name}' 
                    AND indexname = '{self.table_name}_embedding_idx'
                """)
                
                if not cur.fetchone():
                    print(f"[Creating] HNSW index on {count} vectors...")
                    cur.execute(f"""
                        CREATE INDEX {self.table_name}_embedding_idx 
                        ON {self.table_name} 
                        USING hnsw (embedding vector_cosine_ops)
                    """)
                    self.conn.commit()
                    print("[OK] HNSW index created")
        
        return {
            "indexed": len(chunks),
            "total_chunks": len(chunks),
            "table_name": self.table_name
        }
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Semantic search using cosine similarity

        Args:
            query: Search query (Turkish or English)
            top_k: Number of results to return
            filters: Optional filters (e.g., {"page_number": 5})

        Returns:
            List of SearchResult objects sorted by similarity
        """
        # Generate query embedding
        if self.model:
            # Local model (for backward compatibility)
            query_embedding = self.model.encode([query])[0]
        else:
            # Hugging Face API (saves memory!)
            query_embedding = self._encode_via_hf_api(query)
        
        # Build WHERE clause for filters
        where_clause = ""
        filter_values = []
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"{key} = %s")
                filter_values.append(value)
            where_clause = "WHERE " + " AND ".join(conditions)
        
        # Search using cosine similarity
        with self.conn.cursor() as cur:
            query_sql = f"""
                SELECT 
                    chunk_id,
                    text,
                    page_number,
                    paragraph_id,
                    metadata,
                    1 - (embedding <=> %s::vector) as similarity
                FROM {self.table_name}
                {where_clause}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            
            params = [query_embedding.tolist()] + filter_values + [query_embedding.tolist(), top_k]
            cur.execute(query_sql, params)
            
            results = []
            for row in cur.fetchall():
                results.append(SearchResult(
                    chunk_id=row[0],
                    text=row[1],
                    page_number=row[2],
                    paragraph_id=row[3],
                    metadata=row[4] or {},
                    score=float(row[5])  # Cosine similarity (0-1, higher is better)
                ))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get table statistics"""
        with self.conn.cursor() as cur:
            # Count documents
            cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cur.fetchone()[0]
            
            # Get table size
            cur.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{self.table_name}'))
            """)
            size = cur.fetchone()[0]
            
            # Check if index exists
            cur.execute(f"""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = '{self.table_name}'
                AND indexname = '{self.table_name}_embedding_idx'
            """)
            has_index = cur.fetchone() is not None
            
            return {
                "total_documents": count,
                "table_size": size,
                "has_hnsw_index": has_index,
                "table_name": self.table_name,
                "embedding_dimension": self.embedding_dimension
            }
    
    def delete_table(self):
        """Delete the table (use with caution!)"""
        with self.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.table_name} CASCADE")
            self.conn.commit()
            print(f"[OK] Deleted table '{self.table_name}'")
    
    def close(self):
        """Close PostgreSQL connection"""
        self.conn.close()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # Test pgvector store
    print("=== pgvector Store Test ===\n")
    
    load_dotenv()
    
    connection_string = os.getenv("POSTGRES_URL")
    if not connection_string:
        print("ERROR: POSTGRES_URL not found in .env file")
        exit(1)
    
    try:
        store = PgVectorStore(
            connection_string=connection_string,
            table_name="test_embeddings"
        )
        
        # Test indexing
        test_chunks = [
            {
                "chunk_id": "test_001",
                "text": "Amoxicillin is a penicillin antibiotic used to treat bacterial infections.",
                "page_number": 1,
                "paragraph_id": "p_001",
                "document_name": "test.pdf",
                "chunk_index": 0
            },
            {
                "chunk_id": "test_002",
                "text": "Pediatric dosing for amoxicillin is 20-40 mg/kg/day divided into 2-3 doses.",
                "page_number": 2,
                "paragraph_id": "p_002",
                "document_name": "test.pdf",
                "chunk_index": 1
            }
        ]
        
        result = store.index_chunks(test_chunks)
        print(f"\nIndexing result: {result}")
        
        # Test search
        print("\n--- Testing Semantic Search ---")
        results = store.search("how to dose amoxicillin for children", top_k=5)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Similarity: {result.score:.3f}")
            print(f"   Text: {result.text[:100]}...")
            print(f"   Page: {result.page_number}")
        
        # Stats
        print("\n--- Table Stats ---")
        stats = store.get_stats()
        print(f"Total documents: {stats['total_documents']}")
        print(f"Table size: {stats['table_size']}")
        print(f"Has HNSW index: {stats['has_hnsw_index']}")
        
        # Cleanup
        store.delete_table()
        store.close()
        
        print("\n[OK] Test complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()