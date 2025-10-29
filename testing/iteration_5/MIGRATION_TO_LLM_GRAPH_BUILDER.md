# Migration to LLM Graph Builder & Modern GraphRAG Strategies

**Date**: 2025-10-29
**Status**: Planning Phase
**Goal**: Replace pattern-matching KG builders with LLM-based extraction and implement state-of-the-art GraphRAG query enhancement

---

## Executive Summary

### Current Approach (Pattern-Matching)
- ❌ **Brittle**: 800+ hardcoded entity patterns in `medical_kg_builder.py`
- ❌ **Limited Context**: Co-occurrence-based relationships miss semantic meaning
- ❌ **Maintenance Burden**: Requires manual pattern updates for new domains
- ✅ **Results**: 399 nodes, 1,431 relationships (but quality varies)

### New Approach (LLM-Based)
- ✅ **Semantic Understanding**: LLM extracts entities with context
- ✅ **Adaptive**: No manual patterns needed
- ✅ **Better Relationships**: Understands causal, temporal, hierarchical links
- ✅ **Industry Standard**: Following Neo4j Labs best practices (2024-2025)

---

## Part 1: Neo4j LLM Graph Builder

### Overview
[Neo4j Labs LLM Graph Builder](https://github.com/neo4j-labs/llm-graph-builder) is the official tool for constructing knowledge graphs from unstructured data using LLMs.

### Key Features (2025 Release)

#### 1. **LLM-Based Entity & Relationship Extraction**
- Supports: OpenAI GPT-4, Anthropic Claude, Google Gemini, AWS Bedrock, Ollama (local)
- Uses LangChain's `llm-graph-transformer` module
- Extracts entities with semantic understanding (not regex)

#### 2. **Community Detection & Hierarchical Summaries**
- **Leiden Algorithm**: Automatically clusters related entities
- **Hierarchical Summaries**: Generate multi-level summaries for global queries
- **Example**:
  ```
  Community: Neonatal Respiratory Disorders
    ├─ Entities: PPHN, RDS, meconium aspiration, surfactant, ECMO
    └─ Summary: "Persistent pulmonary hypertension (PPHN) and respiratory
                 distress syndrome (RDS) are common in premature infants..."
  ```

#### 3. **Multiple Retrieval Strategies**
- **Vector Search**: Similarity-based chunk retrieval
- **Hybrid Search**: Combines embeddings + full-text search on entities
- **Local Entity Retrieval**: Graph traversal from specific entities
- **Global Community Retrieval**: Uses hierarchical summaries for broad questions

#### 4. **Guided Extraction with Custom Prompts**
```python
# Example: Focus extraction on medical entities
extraction_prompt = """
Extract medical entities focusing on:
- Diseases (with ICD codes if mentioned)
- Medications (generic and brand names)
- Procedures (with CPT codes if available)
- Symptoms and clinical findings
- Anatomical structures

Relationships to identify:
- TREATS (medication → disease)
- CAUSES (condition → symptom)
- DIAGNOSED_BY (disease → procedure)
"""
```

#### 5. **Evaluation & Metrics**
- Integrated RAGAs framework
- Measures: relevancy, faithfulness, semantic similarity
- Compare multiple retrievers in parallel

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  LLM GRAPH BUILDER FLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PDF/Text Documents                                         │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────┐                                       │
│  │  Chunk & Embed   │  Configurable chunking strategy      │
│  └────────┬─────────┘                                       │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────┐                                       │
│  │  LLM Extraction  │  Extract entities + relationships    │
│  └────────┬─────────┘  (GPT-4, Claude, Bedrock, etc.)     │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────┐                                       │
│  │ Community Detect │  Leiden clustering                   │
│  └────────┬─────────┘                                       │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────┐                                       │
│  │ Generate Summary │  Hierarchical summaries              │
│  └────────┬─────────┘                                       │
│           │                                                 │
│           ▼                                                 │
│      Neo4j Graph                                            │
│   (Entities + Communities)                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Options

#### Option 1: Hosted Service (Easiest)
- URL: https://llm-graph-builder.neo4jlabs.com/
- Just upload PDFs, configure LLM, done
- **Limitation**: Data stored on Neo4j Labs infrastructure

#### Option 2: Docker Compose (Recommended for Testing)
```bash
# Clone the repo
git clone https://github.com/neo4j-labs/llm-graph-builder.git
cd llm-graph-builder

# Configure .env
cat > .env << EOF
OPENAI_API_KEY=your_key_here
# OR
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

NEO4J_URI=neo4j+s://your-neo4j-url
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
EOF

# Start services
docker-compose up -d
```

#### Option 3: Python Integration (For Custom Workflows)
```python
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI
from langchain_community.graphs import Neo4jGraph

# Initialize LLM
llm = ChatOpenAI(temperature=0, model_name="gpt-4")

# Initialize graph transformer
llm_transformer = LLMGraphTransformer(llm=llm)

# Connect to Neo4j
graph = Neo4jGraph(
    url="neo4j+s://your-instance.databases.neo4j.io",
    username="neo4j",
    password="your-password"
)

# Transform documents into graph
from langchain.schema import Document
documents = [Document(page_content="Your medical text here...")]
graph_documents = llm_transformer.convert_to_graph_documents(documents)

# Store in Neo4j
graph.add_graph_documents(graph_documents)
```

---

## Part 2: Modern Query Enhancement Strategies

### 2024-2025 State-of-the-Art Approaches

#### 1. **Local Search (Entity-Focused)**
**When to use**: Specific entity queries ("What treats PPHN?", "Side effects of ampicillin")

**Strategy**:
```cypher
// 1. Find entity via hybrid search (vector + full-text)
CALL db.index.fulltext.queryNodes('entityIndex', 'PPHN') YIELD node, score

// 2. Traverse to related entities (multi-hop)
MATCH path = (entity)-[*1..2]-(related)
WHERE entity.name CONTAINS 'PPHN'

// 3. Fetch associated chunks
MATCH (entity)-[:MENTIONED_IN]->(chunk:Chunk)

// 4. Get community context
MATCH (entity)-[:BELONGS_TO]->(community:Community)
RETURN community.summary

// All in one query (~50 lines of Cypher)
```

**Example Output**:
```json
{
  "entity": "PPHN",
  "direct_relations": [
    {"type": "TREATS", "target": "inhaled nitric oxide"},
    {"type": "TREATS", "target": "ECMO"},
    {"type": "HAS_SYMPTOM", "target": "cyanosis"}
  ],
  "related_entities": ["RDS", "meconium aspiration"],
  "chunks": [...],
  "community_summary": "Neonatal respiratory emergencies..."
}
```

#### 2. **Global Search (Topic-Focused)**
**When to use**: Broad questions ("What are main neonatal complications?", "Overview of NICU treatments")

**Strategy**:
```cypher
// 1. Find relevant communities via vector search
CALL db.index.vector.queryNodes('communityEmbeddings', 5, $query_embedding)
YIELD node AS community, score

// 2. Retrieve hierarchical summaries
MATCH (community)-[:HAS_PARENT*0..2]->(parent:Community)
RETURN community.summary, parent.summary

// 3. Generate comprehensive answer from summaries
// (LLM aggregates multiple community summaries)
```

**Example Flow**:
```
Query: "What are common neonatal complications?"
  ↓
Communities Found:
  - Respiratory Disorders (score: 0.89)
  - Cardiovascular Issues (score: 0.85)
  - Infectious Diseases (score: 0.82)
  ↓
LLM aggregates summaries → Comprehensive answer
```

#### 3. **Hybrid Approach (Most Powerful)**
**Combine both strategies in parallel**:

```python
async def hybrid_kg_retrieval(query: str, complexity: str):
    if complexity == "simple_fact":
        # Local search only
        return local_entity_search(query)

    elif complexity == "complex":
        # Run both in parallel
        local_results, global_results = await asyncio.gather(
            local_entity_search(query),
            global_community_search(query)
        )

        # Merge and rank
        return merge_results(local_results, global_results)
```

#### 4. **Text-to-Cypher Generation (Advanced)**
**When to use**: Complex analytical queries requiring custom graph traversals

**Strategy**:
```python
from langchain.chains import GraphCypherQAChain

# Natural language → Cypher → Execute → Answer
chain = GraphCypherQAChain.from_llm(
    llm=ChatOpenAI(model="gpt-4"),
    graph=neo4j_graph,
    verbose=True
)

result = chain.run(
    "What drugs treat diseases caused by PPHN?"
)

# LLM generates:
# MATCH (pphn:Disease {name: 'PPHN'})
#       -[:CAUSES]->(symptom)
#       <-[:TREATS]-(drug:Drug)
# RETURN DISTINCT drug.name
```

**Validation Layer** (Important!):
- Check syntax errors
- Validate entity names exist
- Limit query complexity (prevent graph traversal bombs)
- Timeout after 5 seconds

#### 5. **Dynamic Subgraph Generation**
**Problem**: Full KG too large for context window
**Solution**: Extract relevant subgraph per query

```python
def extract_query_subgraph(query: str, max_nodes: int = 50):
    # 1. Identify key entities from query
    entities = extract_entities_from_query(query)

    # 2. Build subgraph around entities
    subgraph_query = """
    MATCH path = (e:Entity)-[*1..2]-(related)
    WHERE e.name IN $entities
    WITH collect(path) AS paths
    CALL apoc.graph.fromPaths(paths, 'subgraph', {})
    YIELD graph
    RETURN graph
    LIMIT $max_nodes
    """

    # 3. Use subgraph for context (not entire KG)
    return neo4j.run(subgraph_query, entities=entities, max_nodes=max_nodes)
```

---

## Part 3: Implementation Plan

### Phase 1: Evaluation & Testing (Week 1)
1. **Test Neo4j LLM Graph Builder**
   - [ ] Deploy Docker Compose locally
   - [ ] Upload Nelson Pediatrics PDF
   - [ ] Compare quality vs. current pattern-based extraction
   - [ ] Measure: entity coverage, relationship accuracy, community quality

2. **Benchmark Retrieval Strategies**
   - [ ] Implement local search (entity-focused)
   - [ ] Implement global search (community summaries)
   - [ ] Test on Turkish query dataset (15 queries)
   - [ ] Measure: precision, recall, answer quality

### Phase 2: Integration (Week 2)
1. **Replace Graph Construction**
   - [ ] Create `llm_kg_builder.py` using LangChain transformer
   - [ ] Deprecate old builders (move to `deprecated/` folder)
   - [ ] Update `build_knowledge_graph.py` to use new approach

2. **Upgrade Query Enhancement**
   - [ ] Implement `modern_kg_expander.py` with local/global search
   - [ ] Add community detection pipeline
   - [ ] Update `rag_v3.py` to use new strategies

3. **Add Text-to-Cypher**
   - [ ] Implement `cypher_generator.py` with validation
   - [ ] Add query complexity limits
   - [ ] Integrate with RAG v3 workflow

### Phase 3: Production Deployment (Week 3)
1. **API Updates**
   - [ ] Update `api_server.py` to support new retrieval modes
   - [ ] Add endpoint: `/chat?retrieval_mode=local|global|hybrid`
   - [ ] Add evaluation metrics to response

2. **Testing & Validation**
   - [ ] Run full Turkish query suite
   - [ ] A/B test: old vs. new approach
   - [ ] Measure latency impact
   - [ ] Update documentation

---

## Part 4: Code Changes Summary

### Files to CREATE
```
iteration_3/
├── llm_kg_builder.py              # LLM-based graph construction
├── modern_kg_expander.py          # Local + global search strategies
├── community_summarizer.py        # Leiden clustering + summaries
├── cypher_generator.py            # Text-to-Cypher with validation
└── query_strategy_selector.py    # Route query to best strategy
```

### Files to UPDATE
```
iteration_3/
├── rag_v3.py                      # Use modern_kg_expander
├── api_server.py                  # Add retrieval mode options
├── config.py                      # Add LLM Graph Builder settings
└── neo4j_store.py                 # Add community query methods
```

### Files to DEPRECATE
```
iteration_3/deprecated/
├── medical_kg_builder.py          # Old pattern-based
├── medical_kg_builder_*.py        # All variants
├── build_knowledge_graph.py       # Replace with LLM version
└── kg_expander.py                 # Replace with modern version
```

---

## Part 5: Research References

### Key Papers (2024-2025)
1. **GraphRAG (Microsoft Research, 2024)**
   - Paper: [From Local to Global: A Graph RAG Approach](https://arxiv.org/abs/2404.16130)
   - Key: Local entity search + global community summaries
   - Performance: 35% improvement over vector-only RAG

2. **Text-to-Cypher Enhancement (2024)**
   - Paper: [Enhancing KG interactions with Text-to-Cypher](https://www.sciencedirect.com/science/article/pii/S0306457325002213)
   - Key: Context-aware prompting + query validation
   - Performance: 23.6% improvement in component matching

3. **Document GraphRAG (2025)**
   - Paper: [Document GraphRAG for Manufacturing QA](https://www.mdpi.com/2079-9292/14/11/2102)
   - Key: Keyword-based semantic linking
   - Performance: 60% improvement in MRR for customer support

### Tools & Frameworks
- [Neo4j LLM Graph Builder](https://github.com/neo4j-labs/llm-graph-builder) (Official)
- [Microsoft GraphRAG](https://microsoft.github.io/graphrag/) (Open source)
- [LangChain Graph Transformers](https://python.langchain.com/docs/use_cases/graph/)
- [Neo4j GraphAcademy Course](https://graphacademy.neo4j.com/courses/llm-knowledge-graph-construction/)

---

## Part 6: Cost & Performance Considerations

### LLM API Costs (Estimated)
```
For Nelson Pediatrics PDF (~500 chunks):

GPT-4 Turbo:
  - Entity extraction: ~$2-3
  - Community summaries: ~$1-2
  - Total: ~$5 one-time

Claude 3 Sonnet:
  - Entity extraction: ~$1.50-2
  - Community summaries: ~$0.75-1
  - Total: ~$3 one-time

AWS Bedrock (Llama 3.1):
  - Entity extraction: ~$0.50-1
  - Community summaries: ~$0.25-0.50
  - Total: ~$1 one-time

Ollama (Local, Llama 3.1):
  - Cost: $0 (hardware only)
  - Time: 3-5x slower than cloud APIs
```

### Query Latency
```
Current (Pattern-based):
  - KG enrichment: ~1-2s
  - Total: ~8-10s per query

New (LLM-based with communities):
  - Local search: ~1-2s (similar)
  - Global search: ~2-3s (community retrieval)
  - Hybrid: ~3-4s (parallel)
  - Total: ~10-12s per query
```

### Graph Statistics Prediction
```
Current:
  - 399 nodes, 1,431 relationships
  - Pattern-matched entities

Expected with LLM:
  - 500-700 nodes (better entity recognition)
  - 2,000-3,000 relationships (semantic understanding)
  - 50-100 communities (hierarchical structure)
```

---

## Part 7: Next Steps

### Immediate Actions (Today)
1. ✅ Research completed (this document)
2. ⏳ Decision: Test hosted service OR Docker deployment?
3. ⏳ Set up LLM Graph Builder test environment
4. ⏳ Upload Nelson PDF and compare results

### This Week
1. ⏳ Implement local + global search strategies
2. ⏳ Test on Turkish query dataset
3. ⏳ Measure quality improvement

### Next Week
1. ⏳ Integrate with RAG v3
2. ⏳ Update API server
3. ⏳ Deploy to production

---

## Questions for Discussion

1. **LLM Choice**: GPT-4 (best quality) vs. AWS Bedrock (cost-effective) vs. Ollama (privacy)?
2. **Deployment**: Use hosted Neo4j LLM Graph Builder OR self-hosted Docker?
3. **Migration Strategy**: Big bang replacement OR gradual A/B testing?
4. **Community Summaries**: Generate immediately OR lazy (on first query)?
5. **Turkish Support**: How well do English-focused LLMs extract from medical Turkish?

---

**Created**: 2025-10-29
**Next Review**: After initial LLM Graph Builder testing
**Owner**: DoctorFollow Team
