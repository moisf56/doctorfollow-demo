"""
Configuration for DoctorFollow Medical Search Agent
Database connections and model settings
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with validation"""

    # Project paths
    PROJECT_ROOT: Path = Path(__file__).parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    RESULTS_DIR: Path = PROJECT_ROOT / "eval" / "results"

    # OpenSearch
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_INDEX: str = "medical_chunks"

    # PostgreSQL + pgvector
    # Can use either POSTGRES_URL (full connection string) OR individual components
    POSTGRES_URL: Optional[str] = None  # Full connection string (takes priority)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "doctorfollow"
    POSTGRES_USER: str = "doctor"
    POSTGRES_PASSWORD: str = "follow123"
    PGVECTOR_TABLE: str = "embeddings"

    # Neo4j (use neo4j+ssc:// for self-signed certificates in Aura)
    NEO4J_URI: str = "neo4j+ssc://52dba6f2.databases.neo4j.io"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "KRFRRHmIMvw1lcg-MEjWDEtGfHlw8oOX6GvHWKJba3o"

    # AWS Bedrock
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    BEDROCK_MODEL_ID: str = "meta.llama3-1-8b-instruct-v1:0"

    # Embedding models
    # Iteration 1: Not used (OpenSearch only)
    # Iteration 2+: Multilingual for Turkish → English
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    EMBEDDING_DIMENSION: int = 384  # multilingual-e5-small dimension

    # Chunking parameters
    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 100

    # Retrieval parameters
    TOP_K_OPENSEARCH: int = 10
    TOP_K_PGVECTOR: int = 10
    TOP_K_FINAL: int = 3  # After RRF fusion (reduced from 5 to focus on best matches)
    RRF_K: int = 60  # RRF constant

    # LLM parameters
    LLM_TEMPERATURE: float = 0.2  # Low for medical accuracy
    LLM_MAX_TOKENS: int = 512

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_opensearch_url(self) -> str:
        """Get full OpenSearch URL"""
        return f"http://{self.OPENSEARCH_HOST}:{self.OPENSEARCH_PORT}"

    def get_postgres_url(self) -> str:
        """Get PostgreSQL connection string - prioritizes POSTGRES_URL if set"""
        if self.POSTGRES_URL:
            return self.POSTGRES_URL
        # Fallback to individual components
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


# Global settings instance
settings = Settings()

# Create directories if they don't exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # Test configuration
    print("=== DoctorFollow Configuration ===\n")
    print(f"OpenSearch URL: {settings.get_opensearch_url()}")
    print(f"PostgreSQL URL: {settings.get_postgres_url()}")
    print(f"Neo4j URI: {settings.NEO4J_URI}")
    print(f"\nEmbedding Model: {settings.EMBEDDING_MODEL}")
    print(f"Embedding Dimension: {settings.EMBEDDING_DIMENSION}")
    print(f"\nChunk Size: {settings.CHUNK_SIZE}")
    print(f"Chunk Overlap: {settings.CHUNK_OVERLAP}")
    print(f"\nData Directory: {settings.DATA_DIR}")
    print(f"Results Directory: {settings.RESULTS_DIR}")