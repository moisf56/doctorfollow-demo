# Future Improvements & Considerations

**Date:** 2025-10-17
**Status:** Ideas for post-Iteration 5

---

## 1. Multi-LLM Support 🤖

### Goal
Allow users to choose their preferred LLM at runtime

### Proposed LLMs

| Provider | Model | Strengths | Cost | Latency |
|----------|-------|-----------|------|---------|
| **AWS Bedrock** | Llama 4 Scout 17B | Medical reasoning, free tier | $ | ~2s |
| **OpenAI** | GPT-4 | Best general quality, citations | $$$ | ~3s |
| **Anthropic** | Claude 3.5 Sonnet | Long context, safety | $$ | ~2s |
| **Local** | Llama 3.1 8B (Ollama) | Privacy, offline, free | Free | ~5s |

### Implementation Approach

#### Option A: LangChain Model Abstraction
```python
# config.py
LLM_PROVIDER = "bedrock"  # or "openai", "anthropic", "ollama"

# rag_v5.py
def get_llm(provider: str):
    if provider == "bedrock":
        return ChatBedrock(model_id="us.meta.llama4-scout-17b-instruct-v1:0")
    elif provider == "openai":
        return ChatOpenAI(model="gpt-4-turbo-preview")
    elif provider == "anthropic":
        return ChatAnthropic(model="claude-3-5-sonnet-20241022")
    elif provider == "ollama":
        return ChatOllama(model="llama3.1:8b")
```

#### Option B: LangGraph Dynamic Node
```python
# Add LLM selection node
def llm_selector_node(state: MedicalRAGState) -> MedicalRAGState:
    """Route to best LLM based on query complexity"""
    query_complexity = analyze_complexity(state["query"])

    if query_complexity == "simple":
        llm = ChatOllama()  # Fast, local
    elif query_complexity == "medical_complex":
        llm = ChatBedrock()  # Medical-optimized
    else:
        llm = ChatOpenAI()  # Best quality

    return generate_with_llm(llm, state)
```

### Benefits
- ✅ User choice (privacy, cost, quality trade-offs)
- ✅ Fallback if one provider fails
- ✅ A/B testing different models
- ✅ Cost optimization (use cheaper models when sufficient)

### Considerations
- ⚠️ Different prompt engineering per model
- ⚠️ Citation format consistency
- ⚠️ Rate limits per provider
- ⚠️ API key management

---

## 2. Translation Node (Backup Strategy) 🌐

### Context
**Primary Strategy:** Multilingual embeddings (Iteration 2)
**Backup Strategy:** Explicit translation node (if embeddings insufficient)

### When Needed?
If after Iteration 2, Turkish queries still struggle:
- Multilingual embeddings not bridging gap fully
- Domain-specific medical terms lost in embedding space
- Low-resource language challenges

### Implementation

#### LangGraph Translation Node Architecture
```
Turkish Query
    ↓
[Translation Node] → English query
    ↓
[Retrieve Node] → OpenSearch BM25 + pgvector (on English query)
    ↓
[Generate Node] → LLM (English context)
    ↓
[Translate Back Node] → Turkish answer (optional)
```

#### Code Sketch
```python
def translation_node(state: MedicalRAGState) -> MedicalRAGState:
    """Translate Turkish query to English"""
    query = state["query"]

    # Detect language
    if detect_language(query) == "tr":
        # Option 1: AWS Translate
        translated = translate_client.translate_text(
            Text=query,
            SourceLanguageCode='tr',
            TargetLanguageCode='en'
        )

        # Option 2: LLM-based translation
        translated = llm.invoke(
            f"Translate to English (medical context): {query}"
        )

        return {**state, "query": translated, "original_query": query}

    return state
```

### Services to Consider

| Service | Pros | Cons | Cost |
|---------|------|------|------|
| **AWS Translate** | Fast, medical lexicon support | $$ per char | $15/1M chars |
| **Google Translate** | High quality, free tier | Privacy concerns | Free/$ |
| **LLM Translation** | Context-aware, same infrastructure | Slower, costs tokens | Varies |
| **MarianMT (local)** | Free, offline | Lower quality for medical | Free |

### Pros & Cons

#### ✅ Pros
1. **Guaranteed English matching** - BM25 will work perfectly
2. **Medical term precision** - "amoksisilin" → "amoxicillin" exact
3. **Simple implementation** - one node addition
4. **Debuggable** - can inspect translated query

#### ❌ Cons
1. **Extra latency** - +500ms per translation
2. **Translation errors** - medical terms may be mistranslated
3. **Cost** - AWS Translate or LLM tokens
4. **Semantic loss** - idioms, context nuances lost
5. **Two-way problem** - need to translate answer back? (optional)

### Decision Tree
```
Does Turkish query work well? (Iter 2)
    ├─ YES (80%+ accuracy) → ✅ No translation needed
    │                          Multilingual embeddings sufficient
    │
    └─ NO (<80% accuracy) → Add translation node
           ├─ Test: Translation + BM25 + embeddings
           ├─ Measure improvement
           └─ Keep if > 20% accuracy gain
```

### Hybrid Approach (Best of Both)
```python
def hybrid_retrieve_node(state: MedicalRAGState):
    """Retrieve with both strategies, merge results"""

    # Strategy 1: Multilingual embeddings (no translation)
    semantic_results = pgvector.search_multilingual(query)

    # Strategy 2: Translate + BM25
    if detect_language(query) == "tr":
        translated_query = translate(query)
        bm25_results = opensearch.search(translated_query)
    else:
        bm25_results = opensearch.search(query)

    # Merge with RRF
    merged = rrf_fusion(semantic_results, bm25_results)
    return merged
```

---

## 3. Query Analysis Enhancement 🔍

### Extension to Translation Node
Before translating, analyze query intent:

```python
def query_analyzer_node(state: MedicalRAGState):
    """Analyze query before processing"""
    query = state["query"]

    analysis = {
        "language": detect_language(query),
        "intent": classify_intent(query),  # factual, dose_calc, ddi_check
        "entities": extract_entities(query),  # drugs, diseases, age
        "complexity": assess_complexity(query),
        "needs_translation": detect_language(query) != "en"
    }

    return {**state, "query_analysis": analysis}
```

Benefits:
- ✅ Smart routing (translation only if needed)
- ✅ Entity extraction helps retrieval
- ✅ Intent classification triggers tools

---

## 4. Comparative Testing Framework 📊

### Test Multiple Strategies Simultaneously

```python
# evaluation/comparative_test.py
def compare_retrieval_strategies(query: str):
    """Test all strategies in parallel"""

    strategies = {
        "bm25_only": opensearch.search(query),
        "semantic_only": pgvector.search(query),
        "hybrid_no_translation": rrf_fusion(bm25, semantic),
        "hybrid_with_translation": rrf_fusion(
            opensearch.search(translate(query)),
            pgvector.search(query)
        )
    }

    # Evaluate each
    results = {}
    for name, retrieved_chunks in strategies.items():
        answer = llm.generate(query, retrieved_chunks)
        results[name] = evaluate_answer(answer, ground_truth)

    return results
```

**Output:**
```
Query: "Çocuklarda amoksisilin dozu nedir?"

Strategy                    | Recall@5 | Accuracy | Latency
----------------------------|----------|----------|--------
BM25 only                   | 0.2      | 0%       | 50ms
Semantic only               | 0.8      | 70%      | 80ms
Hybrid (no translation)     | 0.9      | 85%      | 100ms
Hybrid (with translation)   | 1.0      | 95%      | 650ms  ← Slower but best
```

---

## 5. LLM Selection Logic 🎯

### Dynamic Model Selection Based on Query

```python
def select_best_llm(query_analysis: dict) -> BaseChatModel:
    """Choose LLM based on query characteristics"""

    # Simple factual query → Fast local model
    if query_analysis["complexity"] == "simple":
        return ChatOllama(model="llama3.1:8b")

    # Medical reasoning → Bedrock (medical-optimized)
    elif query_analysis["intent"] in ["diagnosis", "treatment"]:
        return ChatBedrock(model_id="us.meta.llama4-scout-17b-instruct-v1:0")

    # Complex multi-step → GPT-4 (best reasoning)
    elif query_analysis["complexity"] == "complex":
        return ChatOpenAI(model="gpt-4-turbo")

    # Default
    return ChatBedrock()
```

**Benefits:**
- ✅ Cost-effective (use expensive models only when needed)
- ✅ Speed-optimized (local models for simple queries)
- ✅ Quality-optimized (best models for complex queries)

---

## 6. Implementation Priority

| Feature | Priority | Iteration | Effort | Impact |
|---------|----------|-----------|--------|--------|
| **Multi-LLM support** | 🔴 High | Post-Iter 5 | 2h | High (user choice) |
| **Translation node** | 🟡 Medium | If Iter 2 fails | 1h | Medium (backup) |
| **Query analyzer** | 🟢 Low | Iter 4 | 3h | High (routing) |
| **Comparative testing** | 🟢 Low | Continuous | 2h | High (measurement) |
| **Dynamic LLM selection** | 🟡 Medium | Post-Iter 5 | 2h | Medium (optimization) |

---

## 7. Configuration Structure

### .env additions for multi-LLM
```bash
# LLM Configuration
LLM_PROVIDER=bedrock  # bedrock, openai, anthropic, ollama
LLM_FALLBACK=openai   # Fallback if primary fails

# AWS Bedrock
BEDROCK_MODEL_ID=us.meta.llama4-scout-17b-instruct-v1:0

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Translation
ENABLE_TRANSLATION=false  # Only if multilingual embeddings fail
TRANSLATION_SERVICE=aws_translate  # aws_translate, google, llm
```

---

## 8. Testing Strategy

### A/B Test: Multilingual Embeddings vs Translation

**Setup:**
- 50% Turkish queries → multilingual embeddings only
- 50% Turkish queries → translate to English + BM25

**Metrics:**
- Retrieval quality (Recall@5, Recall@10)
- Answer accuracy (vs ground truth)
- Latency
- Cost per query

**Expected Results:**
```
Multilingual embeddings:
  + Faster (100ms vs 650ms)
  + Cheaper (no translation cost)
  + Better semantic understanding
  - May miss exact medical terms

Translation:
  + Perfect term matching (amoksisilin → amoxicillin)
  + Better BM25 scores
  - Slower
  - More expensive
  - May lose semantic nuance
```

**Decision:** Keep whichever strategy achieves >85% accuracy at lower cost

---

## Conclusion

### Recommended Path Forward

**Immediate (Iterations 2-5):**
1. ✅ Implement multilingual embeddings (Iter 2)
2. ✅ Test thoroughly with Turkish queries
3. ⏸️ Hold translation node as backup

**Post-Iteration 5:**
1. 🔴 Add multi-LLM support (high value, low effort)
2. 🟡 Implement translation node IF needed (<85% Turkish accuracy)
3. 🟢 Add query analyzer for smart routing
4. 🟢 Build comparative testing framework

**Philosophy:**
> "Build the simplest thing that works, measure, then add complexity only if needed"

---

**Notes saved for future implementation!** 📝
