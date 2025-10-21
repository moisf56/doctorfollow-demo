"""
OpenSearch Store for DoctorFollow Medical Search Agent
Iteration 1: BM25 lexical search implementation

Implements BM25 retrieval node (will integrate with LangGraph in Iteration 4)
"""
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch, helpers
from dataclasses import dataclass
import json


@dataclass
class SearchResult:
    """Single search result from OpenSearch"""
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    page_number: Optional[int] = None
    paragraph_id: Optional[str] = None


class OpenSearchStore:
    """
    OpenSearch client for medical document retrieval

    Features:
    - BM25 lexical search
    - Metadata filtering (page, paragraph)
    - Bulk indexing
    """

    def __init__(self, host: str = "localhost", port: int = 9200, index_name: str = "medical_chunks"):
        """
        Initialize OpenSearch connection

        Args:
            host: OpenSearch host
            port: OpenSearch port
            index_name: Index name for storing chunks
        """
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )
        self.index_name = index_name
        self._create_index_if_not_exists()

    def _create_index_if_not_exists(self):
        """Create index with medical-optimized mapping"""
        if self.client.indices.exists(index=self.index_name):
            print(f"[OK] Index '{self.index_name}' already exists")
            return

        # Mapping optimized for medical text
        mapping = {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "medical_analyzer": {
                            "type": "standard",
                            "stopwords": "_english_"  # Keep medical terms
                        }
                    }
                },
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            },
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "text": {
                        "type": "text",
                        "analyzer": "medical_analyzer",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "page_number": {"type": "integer"},
                    "paragraph_id": {"type": "keyword"},
                    "document_name": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "doi": {"type": "keyword"},
                    "pmid": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "year": {"type": "integer"},
                    "timestamp": {"type": "date"}
                }
            }
        }

        self.client.indices.create(index=self.index_name, body=mapping)
        print(f"[OK] Created index '{self.index_name}' with medical mapping")

    def index_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk index chunks to OpenSearch

        Args:
            chunks: List of chunk dictionaries with text and metadata

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

        # Prepare bulk actions
        actions = [
            {
                "_index": self.index_name,
                "_id": chunk.get("chunk_id", f"chunk_{i}"),
                "_source": chunk
            }
            for i, chunk in enumerate(chunks)
        ]

        # Bulk index
        success, failed = helpers.bulk(
            self.client,
            actions,
            stats_only=False,
            raise_on_error=False
        )

        print(f"[OK] Indexed {success} chunks, {len(failed)} failed")

        return {
            "indexed": success,
            "failed": len(failed),
            "total_chunks": len(chunks),
            "index_name": self.index_name
        }

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        BM25 search in OpenSearch

        Args:
            query: Search query (Turkish or English)
            top_k: Number of results to return
            filters: Optional filters (e.g., {"page_number": 5})

        Returns:
            List of SearchResult objects sorted by BM25 score
        """
        # Build query
        query_body = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "text": {
                                    "query": query,
                                    "fuzziness": "AUTO"  # Handle typos
                                }
                            }
                        }
                    ],
                    "filter": []
                }
            },
            "highlight": {
                "fields": {
                    "text": {
                        "fragment_size": 150,
                        "number_of_fragments": 1
                    }
                }
            }
        }

        # Add filters if provided
        if filters:
            for key, value in filters.items():
                query_body["query"]["bool"]["filter"].append(
                    {"term": {key: value}}
                )

        # Execute search
        response = self.client.search(
            index=self.index_name,
            body=query_body
        )

        # Parse results
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            results.append(SearchResult(
                chunk_id=hit['_id'],
                text=source.get('text', ''),
                score=hit['_score'],
                metadata=source,
                page_number=source.get('page_number'),
                paragraph_id=source.get('paragraph_id')
            ))

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        if not self.client.indices.exists(index=self.index_name):
            return {"exists": False}

        stats = self.client.indices.stats(index=self.index_name)
        count = self.client.count(index=self.index_name)

        return {
            "exists": True,
            "total_documents": count['count'],
            "index_size_bytes": stats['indices'][self.index_name]['total']['store']['size_in_bytes'],
            "index_name": self.index_name
        }

    def delete_index(self):
        """Delete the index (use with caution!)"""
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            print(f"[OK] Deleted index '{self.index_name}'")

    def close(self):
        """Close OpenSearch connection"""
        self.client.close()


if __name__ == "__main__":
    # Test OpenSearch connection
    print("=== OpenSearch Store Test ===\n")

    store = OpenSearchStore()

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
    print("\n--- Testing Search ---")
    results = store.search("amoxicillin dose children", top_k=5)

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result.score:.3f}")
        print(f"   Text: {result.text[:100]}...")
        print(f"   Page: {result.page_number}")

    # Stats
    print("\n--- Index Stats ---")
    stats = store.get_stats()
    print(json.dumps(stats, indent=2))

    store.close()
    print("\n[OK] Test complete!")
