"""
pgvector Store for DoctorFollow Medical Search Agent
Iteration 2: Semantic vector search with multilingual embeddings

Implements pgvector retrieval for cross-lingual semantic search
Uses intfloat/multilingual-e5-large for Turkish ↔ English bridging
"""
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class VectorSearchResult:
    """Single search result from pgvector"""
    chunk_id: str
    text: str
    score: float  # Cosine similarity (0-1, higher is better)
    metadata: Dict[str, Any]
    page_number: Optional[int] = None
    paragraph_id: Optional[str] = None


class PgVectorStore:
    """
    PostgreSQL + pgvector client for semantic medical document retrieval

    Features:
    - Multilingual embeddings (intfloat/multilingual-e5-large)
    - Cosine similarity search
    - Efficient indexing with IVFFlat
    - Cross-lingual retrieval (Turkish → English)
    """

    def __init__(
        self,
        connection_string: str,
        table_name: str = "embeddings",
        embedding_model: str = "intfloat/multilingual-e5-large",
        embedding_dimension: int = 1024
    ):
        """
        Initialize pgvector connection

        Args:
            connection_string: PostgreSQL connection string
            table_name: Table name for storing embeddings
            embedding_model: HuggingFace model ID for embeddings
            embedding_dimension: Embedding vector dimension
        """
        self.conn = psycopg2.connect(connection_string)
        self.conn.autocommit = False
        register_vector(self.conn)

        self.table_name = table_name
        self.embedding_dimension = embedding_dimension

        # Load embedding model
        print(f"[Loading] Embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        print(f"[OK] Model loaded (dimension: {embedding_dimension})")

        self._create_extension()
        self._create_table_if_not_exists()

    def _create_extension(self):
        """Enable pgvector extension"""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self.conn.commit()
            print("[OK] pgvector extension enabled")

    def _create_table_if_not_exists(self):
        """Create embeddings table with vector column"""
        with self.conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                )
            """, (self.table_name,))

            exists = cur.fetchone()[0]

            if exists:
                print(f"[OK] Table '{self.table_name}' already exists")
                return

            # Create table
            cur.execute(f"""
                CREATE TABLE {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    chunk_id VARCHAR(255) UNIQUE NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector({self.embedding_dimension}),
                    page_number INTEGER,
                    paragraph_id VARCHAR(255),
                    document_name VARCHAR(255),
                    chunk_index INTEGER,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for fast similarity search
            # Using IVFFlat with 100 lists (good for ~10k-100k vectors)
            cur.execute(f"""
                CREATE INDEX ON {self.table_name}
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

            self.conn.commit()
            print(f"[OK] Created table '{self.table_name}' with vector index")

    def embed_text(self, text: str, prefix: str = "passage: ") -> np.ndarray:
        """
        Generate embedding for text using multilingual-e5-large

        Args:
            text: Input text (Turkish or English)
            prefix: Prefix for multilingual-e5 model

        Returns:
            Embedding vector as numpy array
        """
        # multilingual-e5 models use prefix for better performance
        # "query: " for queries, "passage: " for documents
        embedding = self.embedding_model.encode(
            f"{prefix}{text}",
            normalize_embeddings=True
        )
        return embedding

    def embed_batch(self, texts: List[str], prefix: str = "passage: ") -> np.ndarray:
        """
        Generate embeddings for batch of texts

        Args:
            texts: List of input texts
            prefix: Prefix for multilingual-e5 model ("passage: " or "query: ")

        Returns:
            Array of embeddings (batch_size x embedding_dim)
        """
        # Add prefix for better performance
        prefixed_texts = [f"{prefix}{text}" for text in texts]
        embeddings = self.embedding_model.encode(
            prefixed_texts,
            normalize_embeddings=True,
            show_progress_bar=True
        )
        return embeddings

    def index_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 32) -> Dict[str, Any]:
        """
        Bulk index chunks with embeddings to pgvector

        Args:
            chunks: List of chunk dictionaries with text and metadata
            batch_size: Batch size for embedding generation

        Returns:
            Statistics about indexing

        Example chunk format:
            {
                "chunk_id": "chunk_0001",
                "text": "Amoxicillin dosing...",
                "page_number": 5,
                "paragraph_id": "p_001",
                "document_name": "pediatrics.pdf",
                "chunk_index": 0
            }
        """
        if not chunks:
            return {"error": "No chunks provided"}

        print(f"[Embedding] Generating embeddings for {len(chunks)} chunks...")

        # Generate embeddings in batches to avoid memory issues
        all_embeddings = []
        texts = [chunk["text"] for chunk in chunks]

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = self.embed_batch(batch_texts, prefix="passage: ")
            all_embeddings.append(batch_embeddings)
            print(f"  Embedded {min(i + batch_size, len(texts))}/{len(texts)} chunks")

        embeddings = np.vstack(all_embeddings)

        # Prepare data for insertion
        data = []
        for chunk, embedding in zip(chunks, embeddings):
            data.append((
                chunk.get("chunk_id", f"chunk_{chunk.get('chunk_index', 0)}"),
                chunk["text"],
                embedding.tolist(),  # Convert numpy to list for psycopg2
                chunk.get("page_number"),
                chunk.get("paragraph_id"),
                chunk.get("document_name"),
                chunk.get("chunk_index"),
                psycopg2.extras.Json(chunk)  # Store full chunk as metadata
            ))

        # Bulk insert with ON CONFLICT handling
        print(f"[Inserting] Writing {len(data)} embeddings to PostgreSQL...")
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
                data
            )
            self.conn.commit()

        print(f"[OK] Indexed {len(chunks)} chunks with embeddings")

        return {
            "indexed": len(chunks),
            "failed": 0,
            "total_chunks": len(chunks),
            "table_name": self.table_name,
            "embedding_dimension": self.embedding_dimension
        }

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Semantic similarity search using pgvector

        Args:
            query: Search query (Turkish or English)
            top_k: Number of results to return
            filters: Optional filters (e.g., {"page_number": 5})

        Returns:
            List of VectorSearchResult objects sorted by similarity
        """
        # Generate query embedding with "query: " prefix
        query_embedding = self.embed_text(query, prefix="query: ")

        # Build SQL query
        sql = f"""
            SELECT
                chunk_id,
                text,
                page_number,
                paragraph_id,
                metadata,
                1 - (embedding <=> %s::vector) AS similarity
            FROM {self.table_name}
        """

        params = [query_embedding.tolist()]

        # Add filters if provided
        if filters:
            where_clauses = []
            for key, value in filters.items():
                where_clauses.append(f"{key} = %s")
                params.append(value)
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += f" ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([query_embedding.tolist(), top_k])

        # Execute search
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        # Parse results
        results = []
        for row in rows:
            chunk_id, text, page_number, paragraph_id, metadata, similarity = row
            results.append(VectorSearchResult(
                chunk_id=chunk_id,
                text=text,
                score=float(similarity),  # Cosine similarity (0-1)
                metadata=metadata if metadata else {},
                page_number=page_number,
                paragraph_id=paragraph_id
            ))

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get table statistics"""
        with self.conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                )
            """, (self.table_name,))

            exists = cur.fetchone()[0]

            if not exists:
                return {"exists": False}

            # Get count
            cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cur.fetchone()[0]

            # Get table size
            cur.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{self.table_name}'))
            """)
            size = cur.fetchone()[0]

            return {
                "exists": True,
                "total_documents": count,
                "table_size": size,
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
    # Test pgvector connection and cross-lingual search
    import sys
    sys.path.append('..')
    from config import settings

    print("=== pgvector Store Test ===\n")

    store = PgVectorStore(
        connection_string=settings.get_postgres_url(),
        table_name=settings.PGVECTOR_TABLE,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=settings.EMBEDDING_DIMENSION
    )

    # Test with real medical content
    test_chunks = [
        {
            "chunk_id": "test_001",
            "text": "Amoxicillin is a penicillin antibiotic used to treat bacterial infections. The pediatric dosing for amoxicillin is 20-40 mg/kg/day divided into 2-3 doses.",
            "page_number": 1,
            "paragraph_id": "p_001",
            "document_name": "test_pediatrics.pdf",
            "chunk_index": 0
        },
        {
            "chunk_id": "test_002",
            "text": "Otitis media is treated with antibiotics in most cases. First-line treatment typically includes amoxicillin or amoxicillin-clavulanate.",
            "page_number": 2,
            "paragraph_id": "p_002",
            "document_name": "test_pediatrics.pdf",
            "chunk_index": 1
        },
        {
            "chunk_id": "test_003",
            "text": "For children with penicillin allergy, alternative antibiotics include azithromycin or cephalosporins (if no severe allergy).",
            "page_number": 3,
            "paragraph_id": "p_003",
            "document_name": "test_pediatrics.pdf",
            "chunk_index": 2
        }
    ]

    print("Indexing test chunks...")
    result = store.index_chunks(test_chunks)
    print(f"\nIndexing result: {result}")

    # Test 1: English query
    print("\n" + "="*60)
    print("TEST 1: English Query")
    print("="*60)
    query_en = "What is the amoxicillin dose for children?"
    print(f"Query: {query_en}\n")

    results = store.search(query_en, top_k=3)
    for i, result in enumerate(results, 1):
        print(f"{i}. Similarity: {result.score:.3f}")
        print(f"   Text: {result.text}")
        print(f"   Page: {result.page_number}\n")

    # Test 2: Turkish query (cross-lingual!)
    print("="*60)
    print("TEST 2: Turkish Query (Cross-Lingual Test)")
    print("="*60)
    query_tr = "Çocuklarda amoksisilin dozu nedir?"
    print(f"Query: {query_tr}")
    print(f"(Translation: What is the amoxicillin dose for children?)\n")

    results = store.search(query_tr, top_k=3)
    for i, result in enumerate(results, 1):
        print(f"{i}. Similarity: {result.score:.3f}")
        print(f"   Text: {result.text}")
        print(f"   Page: {result.page_number}\n")

    # Test 3: Another Turkish query
    print("="*60)
    print("TEST 3: Another Turkish Query")
    print("="*60)
    query_tr2 = "Penisilin alerjisi olan çocuklar için alternatif antibiyotikler"
    print(f"Query: {query_tr2}")
    print(f"(Translation: Alternative antibiotics for children with penicillin allergy)\n")

    results = store.search(query_tr2, top_k=3)
    for i, result in enumerate(results, 1):
        print(f"{i}. Similarity: {result.score:.3f}")
        print(f"   Text: {result.text}")
        print(f"   Page: {result.page_number}\n")

    # Stats
    print("="*60)
    print("Table Stats")
    print("="*60)
    stats = store.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

    store.close()
    print("\n[OK] Test complete!")
    print("\nExpected behavior:")
    print("✅ Turkish queries should retrieve the same chunks as English queries")
    print("✅ Similarity scores should be high (>0.7) for relevant content")
    print("✅ This validates multilingual embeddings work for cross-lingual RAG")
