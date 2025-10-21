"""
PDF Ingestion using LangChain Components
Iteration 1: Leverage LangChain's document loaders and text splitters

Following LangChain/LangGraph agentic RAG patterns for smooth integration
"""
from typing import List, Dict, Any
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class MedicalPDFIngestion:
    """
    Medical PDF ingestion using LangChain components

    Benefits:
    - Battle-tested document loading
    - Semantic-aware text splitting
    - Metadata preservation
    - Smooth LangGraph integration later
    """

    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 100,
    ):
        """
        Initialize with LangChain text splitter

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap for context preservation
        """
        # RecursiveCharacterTextSplitter tries to split on:
        # 1. Paragraphs (\n\n)
        # 2. Sentences (. )
        # 3. Words ( )
        # This preserves semantic coherence!
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            # Separators for medical text (in order of preference)
            separators=[
                "\n\n",  # Paragraphs
                "\n",    # Lines
                ". ",    # Sentences
                " ",     # Words
                ""       # Characters (fallback)
            ]
        )

    def load_and_split(self, pdf_path: str) -> List[Document]:
        """
        Load PDF and split into chunks using LangChain

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of LangChain Document objects with metadata
        """
        print(f"[INFO] Loading PDF: {Path(pdf_path).name}")

        # LangChain's PyPDFLoader automatically extracts text per page
        loader = PyPDFLoader(pdf_path)

        # Load all pages
        pages = loader.load()
        print(f"[OK] Loaded {len(pages)} pages")

        # Split into chunks while preserving metadata
        print(f"[INFO] Splitting into semantic chunks...")
        chunks = self.text_splitter.split_documents(pages)

        print(f"[OK] Created {len(chunks)} chunks")
        print(f"[INFO] Avg chunk size: {sum(len(c.page_content) for c in chunks) // len(chunks)} chars")

        return chunks

    def prepare_for_opensearch(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """
        Convert LangChain Documents to OpenSearch-ready format

        Args:
            documents: List of LangChain Document objects

        Returns:
            List of dictionaries ready for OpenSearch indexing
        """
        opensearch_docs = []

        for idx, doc in enumerate(documents):
            # Extract metadata
            page_num = doc.metadata.get('page', 0) + 1  # LangChain uses 0-indexed
            source = doc.metadata.get('source', '')

            opensearch_doc = {
                'chunk_id': f"chunk_{idx:05d}",
                'text': doc.page_content,
                'page_number': page_num,
                'paragraph_id': f"p_{page_num}_{idx}",
                'document_name': Path(source).name if source else 'unknown',
                'chunk_index': idx,
                # Metadata for future use
                'metadata': doc.metadata
            }

            opensearch_docs.append(opensearch_doc)

        return opensearch_docs

    def ingest_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Main pipeline: PDF → LangChain Documents → OpenSearch format

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of OpenSearch-ready documents
        """
        # Load and split using LangChain
        documents = self.load_and_split(pdf_path)

        # Convert to OpenSearch format
        opensearch_docs = self.prepare_for_opensearch(documents)

        return opensearch_docs


if __name__ == "__main__":
    # Test with Pediatrics PDF
    print("=== LangChain PDF Ingestion Test ===\n")

    # Use absolute path relative to testing directory
    testing_dir = Path(__file__).parent.parent
    pdf_path = testing_dir / "data" / "Nelson-essentials-of-pediatrics-233-282.pdf"

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found at: {pdf_path}")
        print(f"[INFO] Please ensure the PDF is in: testing/data/")
        exit(1)

    # Initialize
    ingestion = MedicalPDFIngestion(
        chunk_size=400,
        chunk_overlap=100
    )

    # Process PDF
    chunks = ingestion.ingest_pdf(str(pdf_path))

    # Show sample chunks
    print(f"\n--- Sample Chunks ---")
    for i in range(min(3, len(chunks))):
        chunk = chunks[i]
        print(f"\nChunk {i+1}:")
        print(f"  ID: {chunk['chunk_id']}")
        print(f"  Page: {chunk['page_number']}")
        print(f"  Length: {len(chunk['text'])} chars")
        print(f"  Text preview: {chunk['text'][:150]}...")

    print(f"\n[OK] Processed {len(chunks)} total chunks")
    print(f"[INFO] Ready for OpenSearch indexing!")
