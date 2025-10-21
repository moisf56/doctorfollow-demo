# DoctorFollow Medical Search Agent - Iterative Build

**Vision:** Build → Measure → Learn (Lean Startup Style)

## Architecture (Final State)

- **OpenSearch:** BM25 lexical search
- **pgvector:** Semantic vector search (multilingual)
- **Neo4j:** Medical knowledge graph
- **LangGraph:** Agentic orchestration
- **AWS Bedrock:** LLM (Llama 3.1 or Claude)

## Source Data

- **PDF:** Nelson Essentials of Pediatrics (Chapter 11) - English
- **Queries:** Turkish (medical questions)
- **Challenge:** Cross-lingual retrieval (Turkish → English)

## Iteration Plan

### Baseline
- Simple in-memory BM25 + embeddings
- **Measure:** Establish baseline metrics

### Iteration 1: OpenSearch
- Replace in-memory BM25 with OpenSearch
- **Measure:** Latency, recall, Turkish→English matching

### Iteration 2: pgvector
- Replace in-memory embeddings with pgvector
- Switch to multilingual model
- Implement RRF fusion
- **Measure:** Semantic quality, cross-lingual performance

### Iteration 3: Neo4j Knowledge Graph
- Extract medical entities (Disease, Drug, Symptom, Dose)
- Build relationships
- Add KG expansion to retrieval
- Detect contradictions
- **Measure:** Context enrichment, contradiction detection

### Iteration 4: LangGraph Agents
- Query analyzer
- Tool routing (dose calculator, DDI checker, BSA)
- Function calling
- **Measure:** Routing accuracy, tool usage

### Iteration 5: Claims & Attribution
- Claim decomposition
- Source attribution
- Structured JSON output
- **Measure:** Citation accuracy, groundedness

## Project Structure

```
testing/
├── README.md                  # This file
├── requirements.txt           # Dependencies
├── config.py                  # Database configs
├── docker-compose.yml         # OpenSearch + PostgreSQL + Neo4j
│
├── data/
│   ├── Nelson-essentials-of-pediatrics-233-282.pdf
│   └── turkish_queries.json   # Evaluation dataset
│
├── baseline/
│   └── simple_rag.py          # Baseline system
│
├── iteration_1_opensearch/
│   ├── opensearch_store.py
│   └── rag_with_opensearch.py
│
├── iteration_2_pgvector/
│   ├── pgvector_store.py
│   ├── rrf_fusion.py
│   └── rag_with_hybrid.py
│
├── iteration_3_neo4j/
│   ├── neo4j_store.py
│   ├── medical_kg_builder.py
│   ├── contradiction_detector.py
│   └── rag_with_kg.py
│
├── iteration_4_langgraph/
│   ├── nodes/
│   │   ├── query_analyzer.py
│   │   ├── retrieval_node.py
│   │   ├── kg_lookup_node.py
│   │   ├── llm_generator_node.py
│   │   └── function_executor_node.py
│   ├── tools/
│   │   └── medical_tools.py
│   └── graph.py                # LangGraph workflow
│
├── iteration_5_claims/
│   ├── claim_decomposer.py
│   ├── output_schema.py
│   └── final_rag.py
│
├── eval/
│   ├── metrics.py              # Metrics tracking
│   ├── evaluator.py            # Evaluation runner
│   └── results/                # JSON results per iteration
│
└── demo.py                     # Gradio interface
```

## References

- [LangGraph Agentic RAG](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- [pgvector](https://github.com/pgvector/pgvector)
- [Neo4j RAG Tutorial](https://neo4j.com/blog/developer/rag-tutorial/)

## Getting Started

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start infrastructure
docker-compose up -d

# 3. Run baseline
python baseline/simple_rag.py

# 4. Run evaluation
python eval/evaluator.py --iteration baseline

# 5. Iterate!
```
