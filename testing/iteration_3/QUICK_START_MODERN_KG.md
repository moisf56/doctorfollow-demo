# Quick Start: Modern KG with Neo4j LLM Graph Builder

**Last Updated**: 2025-10-29

---

## Option 1: Hosted Service (Fastest - 10 minutes)

### Step 1: Access the Tool
Visit: https://llm-graph-builder.neo4jlabs.com/

### Step 2: Connect Your Neo4j Instance
```
Neo4j URI: neo4j+ssc://52dba6f2.databases.neo4j.io
Username: neo4j
Password: [from .env]
```

### Step 3: Configure LLM
**Recommended for Medical Data**: GPT-4 or Claude 3 Sonnet

```json
{
  "model": "gpt-4-turbo",
  "temperature": 0.0,
  "extraction_prompt": "Extract medical entities: diseases, drugs, procedures, symptoms, anatomical structures. Identify relationships: TREATS, CAUSES, HAS_SYMPTOM, USED_FOR, PREVENTS, DIAGNOSED_BY."
}
```

### Step 4: Upload PDF
Upload: `testing/Nelson-essentials-of-pediatrics.pdf`

### Step 5: Extract & Visualize
- Click "Extract Knowledge Graph"
- Wait 5-10 minutes
- View in Neo4j Bloom

**That's it!** Your graph is ready.

---

## Option 2: Docker Compose (Recommended for Development)

### Prerequisites
```bash
# Check if you have Docker
docker --version
docker-compose --version
```

### Step 1: Clone the Repository
```bash
cd doctorfollow-demo/testing/iteration_3
git clone https://github.com/neo4j-labs/llm-graph-builder.git
cd llm-graph-builder
```

### Step 2: Configure Environment
```bash
# Create .env file
cat > .env << 'EOF'
# LLM Configuration (choose one)
OPENAI_API_KEY=your_openai_key_here
# OR
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Neo4j Connection
NEO4J_URI=neo4j+ssc://52dba6f2.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here

# Optional: Chunking Configuration
CHUNK_SIZE=400
CHUNK_OVERLAP=100

# Optional: Community Detection
ENABLE_COMMUNITIES=true
COMMUNITY_ALGORITHM=leiden
EOF
```

### Step 3: Start Services
```bash
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Step 4: Access UI
Open browser: http://localhost:8000

Upload PDF and extract!

### Step 5: Stop Services
```bash
docker-compose down
```

---

## Option 3: Python Integration (Custom Workflow)

### Installation
```bash
cd doctorfollow-demo/testing
./venvsdoctorfollow/Scripts/activate  # Windows
# OR
source venvsdoctorfollow/bin/activate  # Linux/Mac

pip install langchain-experimental langchain-openai neo4j
```

### Basic Implementation
Create: `iteration_3/llm_kg_builder_basic.py`

```python
"""
Basic LLM Graph Builder using LangChain
"""
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI
from langchain_community.graphs import Neo4jGraph
from langchain.schema import Document
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM
llm = ChatOpenAI(
    temperature=0,
    model_name="gpt-4-turbo",  # or "gpt-3.5-turbo" for cheaper
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# Initialize transformer
llm_transformer = LLMGraphTransformer(
    llm=llm,
    allowed_nodes=["Disease", "Drug", "Procedure", "Symptom", "Anatomy"],
    allowed_relationships=["TREATS", "CAUSES", "HAS_SYMPTOM", "USED_FOR", "PREVENTS", "DIAGNOSED_BY"]
)

# Connect to Neo4j
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD")
)

# Load your PDF chunks (from Elasticsearch)
from iteration_1.opensearch_store import ElasticsearchStore
es = ElasticsearchStore()
chunks = es.search("neonatal infant respiratory", top_k=50)

# Convert chunks to documents
documents = [
    Document(
        page_content=chunk.text,
        metadata={
            "chunk_id": chunk.chunk_id,
            "page_number": chunk.page_number
        }
    )
    for chunk in chunks
]

# Transform to graph documents
print(f"Processing {len(documents)} chunks...")
graph_documents = llm_transformer.convert_to_graph_documents(documents)

# Store in Neo4j
print(f"Storing {len(graph_documents)} graph documents in Neo4j...")
graph.add_graph_documents(graph_documents)

print("Done! Check Neo4j Browser to see your graph.")
```

### Run It
```bash
cd doctorfollow-demo/testing/iteration_3
../venvsdoctorfollow/Scripts/python.exe llm_kg_builder_basic.py
```

---

## Testing the New Graph

### Query 1: Count Entities
```cypher
MATCH (n)
RETURN labels(n)[0] AS type, count(n) AS count
ORDER BY count DESC
```

### Query 2: Check Relationships
```cypher
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(r) AS count
ORDER BY count DESC
LIMIT 10
```

### Query 3: Find Treatment for PPHN
```cypher
MATCH (d:Disease {name: 'PPHN'})<-[:TREATS]-(treatment)
RETURN treatment.name, labels(treatment)[0] AS type
```

### Query 4: Community Detection
```cypher
CALL gds.leiden.stream('myGraph')
YIELD nodeId, communityId
RETURN gds.util.asNode(nodeId).name AS entity, communityId
ORDER BY communityId
LIMIT 20
```

---

## Comparison: Old vs New

### Old Approach (Pattern-Based)
```python
# medical_kg_builder.py - Lines 44-304
entity_patterns = {
    "disease": [
        "PPHN", "RDS", "sepsis",  # 150+ hardcoded patterns
        ...
    ]
}

# Simple co-occurrence
if disease in text and drug in text:
    relationships.append((drug, disease, "TREATS"))
```

**Problems**:
- ❌ Misses variations ("persistent pulmonary hypertension" vs "PPHN")
- ❌ False positives (both words appear but not related)
- ❌ No context understanding
- ❌ Requires constant maintenance

### New Approach (LLM-Based)
```python
# LLM reads: "Treatment for PPHN includes inhaled nitric oxide..."
# Extracts:
#   Entity: PPHN (Disease)
#   Entity: inhaled nitric oxide (Drug)
#   Relationship: (inhaled nitric oxide)-[:TREATS]->(PPHN)
#   Context: "used for pulmonary vasodilation"
```

**Advantages**:
- ✅ Understands context and semantics
- ✅ Handles synonyms automatically
- ✅ Extracts complex relationships
- ✅ No pattern maintenance needed

---

## Cost Estimate

For Nelson Pediatrics PDF (500 chunks):

| Provider | Model | Cost | Time |
|----------|-------|------|------|
| OpenAI | GPT-4 Turbo | ~$3-5 | 10-15 min |
| OpenAI | GPT-3.5 Turbo | ~$0.50-1 | 5-10 min |
| Anthropic | Claude 3 Sonnet | ~$2-3 | 10-15 min |
| AWS Bedrock | Claude 3 Sonnet | ~$2-3 | 10-15 min |
| AWS Bedrock | Llama 3.1 | ~$0.50-1 | 15-20 min |
| Ollama | Llama 3.1 (local) | $0 | 30-60 min |

**Recommendation**: Start with GPT-3.5-Turbo for testing, upgrade to GPT-4 for production.

---

## Next Steps

### 1. Test LLM Graph Builder
- [ ] Choose deployment option (hosted/docker/python)
- [ ] Extract graph from Nelson PDF
- [ ] Compare with existing graph (399 nodes, 1,431 edges)

### 2. Implement Modern Query Strategies
- [ ] Local search (entity-focused)
- [ ] Global search (community summaries)
- [ ] Hybrid approach

### 3. Update RAG v3
- [ ] Replace `kg_expander.py` with modern version
- [ ] Add retrieval mode selection
- [ ] Test on Turkish query dataset

### 4. Measure Improvement
- [ ] Run A/B test: old vs new
- [ ] Metrics: precision, recall, answer quality
- [ ] Latency impact

---

## Troubleshooting

### Issue: "Connection refused to Neo4j"
**Solution**: Use `neo4j+ssc://` scheme for Aura (not `neo4j://`)

### Issue: "API key not found"
**Solution**: Check `.env` file, ensure `OPENAI_API_KEY` or AWS credentials are set

### Issue: "Too many tokens"
**Solution**: Reduce `CHUNK_SIZE` in config (try 300 instead of 400)

### Issue: "Extraction is slow"
**Solution**:
- Use GPT-3.5 instead of GPT-4
- Process in batches (50 chunks at a time)
- Consider Ollama for local processing

### Issue: "LLM extracts irrelevant entities"
**Solution**: Add custom extraction prompt with specific entity types

---

## Resources

### Documentation
- [Neo4j LLM Graph Builder Docs](https://neo4j.com/labs/genai-ecosystem/llm-graph-builder/)
- [LangChain Graph Transformers](https://python.langchain.com/docs/use_cases/graph/)
- [GraphAcademy Course](https://graphacademy.neo4j.com/courses/llm-knowledge-graph-construction/)

### GitHub
- [LLM Graph Builder Repo](https://github.com/neo4j-labs/llm-graph-builder)
- [Example Notebooks](https://github.com/neo4j-labs/llm-graph-builder/tree/main/examples)

### Research Papers
- [GraphRAG (Microsoft, 2024)](https://arxiv.org/abs/2404.16130)
- [LLM-based KG Construction Survey](https://arxiv.org/abs/2310.04835)

---

**Ready to start?** Pick an option above and let's build a better knowledge graph! 🚀
