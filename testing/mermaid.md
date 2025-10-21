# Medical RAG Architecture (Mermaid)

## Detailed Pipeline Flow

```mermaid
flowchart TD
    Start[User Query] --> Step1

    Step1[1. Query Analyzer<br/>- Classify Intent<br/>- Extract Entities<br/>- Check for function trigger dose/DDI/BSA]

    Step1 --> Step2A[2A. Text Retrieval BM25 + pgvector]

    Step2A --> BM25[BM25 Results]
    Step2A --> Vector[Vector Results]

    BM25 --> Step3[3. RRF Fusion]
    Vector --> Step3

    Step3 --> Step4[4. KG Lookup Node<br/>- For entities found<br/>- Retrieve structured triples<br/>- Boost RRF results]

    Step4 --> Step5[5. Context Builder<br/>- Merge ranked text + KG facts<br/>- Format into prompt context]

    Step5 --> Step6[6. LLM Generator<br/>- Produce Answer<br/>- Or request function call]

    Step6 --> Decision{Function?<br/>Does LLM ask<br/>for function?}

    Decision -->|Yes| Step7[7. Execute<br/>Dose/DDI/BSA]
    Decision -->|No| Step8

    Step7 --> Step8[8. Claim Scoring &<br/>Citation Check]

    Step8 --> Step9[9. Final Formatter<br/>Answer JSON]
```

## High-Level Architecture

```mermaid
flowchart TD
    %% User Entry
    User["User Query"] --> Guardrails{"Guardrails / PII Masking"}

    %% Routing Decisions
    Guardrails --> Router{"Query Router"}
    Router -->|Factual / Medical Question| RetrievalPipeline
    Router -->|Dose / DDI / Clinical Tool Use| Tools
    Router -->|Unsafe| Blocked["Refused Response"]

    %% Retrieval Layer
    subgraph RetrievalPipeline[Retrieval Pipeline]
        BM25["BM25 Search - OpenSearch"]
        Embeddings["Semantic Search - pgvector"]
        BM25 --> RRF[RRF Fusion]
        Embeddings --> RRF
    end

    %% Graph & Context Layer
    RRF --> GraphLookup["Knowledge Graph Lookup"]
    GraphLookup --> Context["Context Builder - Chunks + Metadata + Citations"]

    %% LLM Orchestration
    Context --> LLM["Medical LLM - e.g. Meditron, PubMedGPT"]
    Tools --> LLM

    %% Post-Processing
    LLM --> ClaimDecompose["Claim Decomposition"]
    ClaimDecompose --> CitationLinking["Source Attribution - PMID / DOI"]
    CitationLinking --> ContradictionCheck["Contradiction Detection"]
    ContradictionCheck --> FinalAnswer["Cited Answer Returned"]

    %% Return Path
    FinalAnswer --> User
