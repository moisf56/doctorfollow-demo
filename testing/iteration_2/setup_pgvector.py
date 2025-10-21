"""
Setup pgvector extension in PostgreSQL
Run this once before using pgvector_store
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import psycopg2
from config import settings


def setup_pgvector():
    """Enable pgvector extension in the database"""
    print("="*70)
    print("Setting up pgvector extension")
    print("="*70)
    print()

    # Connect to PostgreSQL
    print(f"Connecting to: {settings.get_postgres_url()}")
    conn = psycopg2.connect(settings.get_postgres_url())
    conn.autocommit = True

    with conn.cursor() as cur:
        # Enable pgvector extension
        print("[INFO] Creating vector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("[OK] pgvector extension enabled")

        # Verify it's installed
        cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
        result = cur.fetchone()

        if result:
            print(f"[OK] pgvector version {result[1]} is installed")
        else:
            print("[ERROR] pgvector extension not found!")

    conn.close()
    print()
    print("[OK] Setup complete! You can now run index_embeddings.py")


if __name__ == "__main__":
    setup_pgvector()
