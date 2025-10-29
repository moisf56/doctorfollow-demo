# Answer Grading Rubric: GraphRAG Medical QA

**Purpose**: Evaluate answer quality for Turkish medical queries with English sources
**Version**: 1.0
**Date**: 2025-10-29

---

## 📋 Evaluation Dimensions (8 Criteria)

### 1. **Language Match** (Critical) - Weight: 15%
**Question**: Is the response in the correct language?

| Score | Criteria | Example |
|-------|----------|---------|
| ✅ 5 | 100% target language, professional medical terminology | All Turkish, proper medical terms |
| ⚠️ 3 | Mostly target language, some English medical terms mixed in | Mostly Turkish, "apnea episodes" not translated |
| ❌ 1 | Wrong language or heavy code-switching | English response to Turkish query |
| ❌ 0 | Completely wrong language | - |

**Your Answer Evaluation**:
- ✅ **Score: 5/5** - Perfect Turkish throughout
- Uses proper medical terminology: "prematüre bebekler", "apne epizodları", "solunum merkezi"

---

### 2. **Medical Accuracy** (Critical) - Weight: 25%
**Question**: Is the medical information factually correct?

| Score | Criteria | Details |
|-------|----------|---------|
| ✅ 5 | Completely accurate, up-to-date medical information | Matches medical literature |
| ⚠️ 4 | Mostly accurate, minor details could be improved | 1-2 small inaccuracies |
| ⚠️ 3 | Partially accurate, some outdated or incomplete info | Missing key information |
| ❌ 2 | Significant inaccuracies or misleading statements | Could harm patient care |
| ❌ 0 | Dangerous misinformation | - |

**Your Answer Evaluation**:
- ✅ **Score: 5/5** - Medically accurate
- Correctly identifies: apnea of prematurity, immature respiratory center, respiratory distress syndrome
- Accurate treatment: caffeine citrate for apnea episodes
- Proper monitoring: mechanical ventilation, oxygen support

---

### 3. **Clinical Reasoning** (Important) - Weight: 15%
**Question**: Does the answer show logical medical reasoning?

| Score | Criteria | Example |
|-------|----------|---------|
| ✅ 5 | Strong clinical reasoning, explains pathophysiology | Explains WHY (immature CNS → apnea) |
| ⚠️ 4 | Good reasoning, minor gaps in explanation | States facts without mechanism |
| ⚠️ 3 | Basic reasoning, lacks depth | Lists symptoms without context |
| ❌ 2 | Weak reasoning, jumps to conclusions | - |
| ❌ 0 | No reasoning or illogical | - |

**Your Answer Evaluation**:
- ✅ **Score: 5/5** - Excellent clinical reasoning
- **Pathophysiology**: Explains apnea is due to immature CNS/respiratory center
- **Context**: Notes that respiratory distress syndrome can also occur
- **Treatment rationale**: Caffeine stimulates respiratory center, reduces apnea frequency

---

### 4. **Entity Coverage** (KG Quality Indicator) - Weight: 15%
**Question**: Are key medical entities from the query mentioned?

**Expected Entities** (from query):
- 35 haftalık (35 weeks)
- prematüre bebek (premature infant)
- postnatal 3. gün (postnatal day 3)
- apne epizodları (apnea episodes)
- bradikardi (bradycardia)
- ateş yok (no fever)
- vital bulgular stabil (stable vitals)

| Score | Criteria | Coverage |
|-------|----------|----------|
| ✅ 5 | All key entities addressed (6-7 entities) | 85-100% |
| ⚠️ 4 | Most key entities addressed (4-5 entities) | 60-85% |
| ⚠️ 3 | Some key entities addressed (3 entities) | 40-60% |
| ❌ 2 | Few entities (1-2) | 20-40% |
| ❌ 0 | No entities from query | 0-20% |

**Your Answer Evaluation**:
- ✅ **Score: 4/5** - Most entities covered
- ✅ Prematüre bebek (mentioned)
- ✅ Apne epizodları (main focus)
- ✅ Bradikardi (mentioned as associated)
- ✅ Vital bulgular stabil (addressed in monitoring)
- ⚠️ Postnatal 3. gün (not explicitly mentioned but implied)
- ⚠️ 35 haftalık (gestational age not emphasized)

---

### 5. **Source Citation** (Transparency) - Weight: 10%
**Question**: Are sources properly cited?

| Score | Criteria | Format |
|-------|----------|--------|
| ✅ 5 | All claims cited with [Source N] format | Multiple sources, clear attribution |
| ⚠️ 4 | Most claims cited, 1-2 missing | Good citation coverage |
| ⚠️ 3 | Some citations, inconsistent | Half of claims cited |
| ❌ 2 | Minimal citations | Only 1-2 sources |
| ❌ 0 | No citations | No [Source N] tags |

**Your Answer Evaluation**:
- ✅ **Score: 5/5** - Proper citation
- [Source 3] - Main apnea information
- [Source 2] - Treatment (caffeine citrate)
- Clear attribution for medical claims

---

### 6. **KG Enrichment Evidence** (GraphRAG Quality) - Weight: 10%
**Question**: Is there evidence of knowledge graph usage?

**Indicators of KG Usage**:
- Related entities mentioned (e.g., related conditions)
- Relationship traversal (e.g., TREATS relationships)
- Multi-hop reasoning (e.g., condition → symptom → treatment)
- Contextual connections not in direct chunks

| Score | Criteria | Evidence |
|-------|----------|----------|
| ✅ 5 | Clear KG enrichment, multi-hop connections | Mentions related entities/relationships |
| ⚠️ 4 | Some KG enrichment visible | 1-2 related concepts |
| ⚠️ 3 | Minimal KG usage | Could be from chunks alone |
| ❌ 2 | Little evidence of KG | - |
| ❌ 0 | No KG enrichment | Vector search only |

**Your Answer Evaluation**:
- ✅ **Score: 4/5** - Good KG enrichment evidence
- **Related condition**: Mentions "solunum sıkıntısı sendromu" (RDS) as co-occurring
- **Pathophysiology link**: Connects apnea → immature CNS (relationship)
- **Treatment connection**: Caffeine → reduces apnea frequency (TREATS relationship)
- **Could be better**: Could mention more related complications or alternative treatments

---

### 7. **Completeness** (Coverage) - Weight: 5%
**Question**: Does the answer address all parts of the question?

**Question asked**: "Bu durumun en olası nedeni nedir ve hangi tedavi önerilir?"
(What is the most likely cause and what treatment is recommended?)

| Score | Criteria | Coverage |
|-------|----------|----------|
| ✅ 5 | All parts thoroughly answered | Cause + treatment + context |
| ⚠️ 4 | All parts answered, some brief | Cause + treatment |
| ⚠️ 3 | Main parts answered, gaps exist | Only cause OR only treatment |
| ❌ 2 | Partial answer | Missing major components |
| ❌ 0 | Question not answered | Off-topic |

**Your Answer Evaluation**:
- ✅ **Score: 5/5** - Complete answer
- ✅ **Cause**: Prematüre apne (apnea of prematurity) due to immature CNS
- ✅ **Treatment**: Caffeine citrate (primary), mechanical ventilation (if needed)
- ✅ **Monitoring**: Vital signs, additional interventions
- ✅ **Context**: Mentions RDS as differential/co-morbidity

---

### 8. **Fluency & Professionalism** (Quality) - Weight: 5%
**Question**: Is the language natural and professional?

| Score | Criteria | Quality |
|-------|----------|---------|
| ✅ 5 | Native-level fluency, professional medical tone | Perfect grammar, appropriate terminology |
| ⚠️ 4 | Good fluency, minor awkwardness | 1-2 grammatical issues |
| ⚠️ 3 | Understandable but unnatural | Translation-like quality |
| ❌ 2 | Poor fluency, hard to understand | Multiple errors |
| ❌ 0 | Incomprehensible | - |

**Your Answer Evaluation**:
- ✅ **Score: 5/5** - Excellent fluency
- Natural Turkish medical language
- Proper sentence structure
- Professional tone appropriate for medical context

---

## 📊 Overall Score Calculation

### Your Answer Scores:
| Dimension | Weight | Score | Weighted Score |
|-----------|--------|-------|----------------|
| 1. Language Match | 15% | 5/5 | 0.75 |
| 2. Medical Accuracy | 25% | 5/5 | 1.25 |
| 3. Clinical Reasoning | 15% | 5/5 | 0.75 |
| 4. Entity Coverage | 15% | 4/5 | 0.60 |
| 5. Source Citation | 10% | 5/5 | 0.50 |
| 6. KG Enrichment | 10% | 4/5 | 0.40 |
| 7. Completeness | 5% | 5/5 | 0.25 |
| 8. Fluency | 5% | 5/5 | 0.25 |
| **TOTAL** | **100%** | - | **4.75/5** |

### Final Grade: **4.75/5 (95%) - Excellent** ⭐⭐⭐⭐⭐

---

## 📈 Performance Interpretation

### Grade Bands:
- **4.5-5.0 (90-100%)**: ⭐⭐⭐⭐⭐ Excellent - Production ready
- **4.0-4.5 (80-90%)**: ⭐⭐⭐⭐ Very Good - Minor improvements needed
- **3.5-4.0 (70-80%)**: ⭐⭐⭐ Good - Some gaps, needs refinement
- **3.0-3.5 (60-70%)**: ⭐⭐ Fair - Significant improvements needed
- **<3.0 (<60%)**: ⭐ Poor - Major issues, not production ready

---

## 🎯 Detailed Feedback for This Answer

### ✅ Strengths:
1. **Perfect language match** - No English leakage, proper Turkish medical terms
2. **Medically accurate** - Correct diagnosis (apnea of prematurity)
3. **Strong clinical reasoning** - Explains pathophysiology clearly
4. **Good treatment guidance** - Caffeine citrate as first-line
5. **Proper citations** - [Source 2], [Source 3] clearly marked
6. **Complete answer** - Addresses both "nedir" and "hangi tedavi"

### ⚠️ Areas for Improvement:
1. **Entity coverage** - Could explicitly mention "35 haftalık" (gestational age)
2. **KG enrichment depth** - Could mention:
   - Other apnea causes (differential diagnosis)
   - Related complications (IVH, NEC)
   - Alternative treatments (CPAP, theophylline)
   - Long-term outcomes

### 💡 Suggestions:
To reach perfect 5.0:
- Mention gestational age (35 weeks) as risk factor
- Add 1-2 related complications from KG
- Mention monitoring parameters (SpO2, heart rate thresholds)

---

## 🔄 Comparison: Before vs After Modern KG

### Expected Improvements with Modern KG:
| Metric | Old KG (Pattern) | New KG (LLM) | Improvement |
|--------|------------------|--------------|-------------|
| Entity Coverage | 3.0-3.5 | 4.0-5.0 | +25% |
| KG Enrichment | 2.0-3.0 | 4.0-5.0 | +50% |
| Clinical Reasoning | 3.5-4.0 | 4.5-5.0 | +15% |
| Overall Score | 3.5-4.0 | 4.5-5.0 | +20% |

---

## 📝 How to Use This Rubric

### For Manual Evaluation:
1. Read the query and answer
2. Score each dimension (1-5)
3. Calculate weighted score
4. Compare to grade bands
5. Write feedback (strengths + improvements)

### For A/B Testing:
1. Run same query on old vs new system
2. Grade both answers using this rubric
3. Compare scores across dimensions
4. Look for KG enrichment improvement (Dimension 6)

### For Dataset Evaluation:
1. Grade 10-15 diverse queries
2. Average scores per dimension
3. Identify patterns (which queries benefit most from KG?)
4. Calculate overall system performance

---

## 🤖 Automated Grading (Future)

Could use LLM as judge:
```python
def llm_grade_answer(query, answer, sources):
    prompt = f"""
    Grade this medical answer using the 8-dimension rubric:

    Query: {query}
    Answer: {answer}

    For each dimension (1-8), provide:
    - Score (1-5)
    - Justification (2-3 sentences)

    Return JSON format.
    """
    # Use GPT-4 to grade
    return llm(prompt)
```

---

## 📊 Sample Evaluation Results

### Your Answer:
```json
{
  "query": "35 haftalık prematüre bir bebek, postnatal 3. günde apne epizodları...",
  "answer_grade": {
    "language_match": 5,
    "medical_accuracy": 5,
    "clinical_reasoning": 5,
    "entity_coverage": 4,
    "source_citation": 5,
    "kg_enrichment": 4,
    "completeness": 5,
    "fluency": 5,
    "total_score": 4.75,
    "grade": "Excellent",
    "production_ready": true
  },
  "feedback": {
    "strengths": [
      "Perfect Turkish language",
      "Medically accurate diagnosis",
      "Strong pathophysiology explanation",
      "Good treatment guidance"
    ],
    "improvements": [
      "Mention gestational age explicitly",
      "Add related complications from KG"
    ]
  }
}
```

---

## 🎓 Training Examples

### Example 1: Perfect Answer (5.0)
```
Query: "PPHN tedavisi nedir?"
Answer: "PPHN (Persistan Pulmoner Hipertansiyon), yenidoğanlarda pulmoner
vasküler direncin yüksek kalması sonucu gelişir. Tedavi yaklaşımı:
1) İnhale nitrik oksit (iNO) - pulmoner vazodilatör [Source 1]
2) Yüksek frekanslı ventilasyon [Source 2]
3) ECMO (ciddi vakalarda) [Source 3]
İlişkili durumlar: RDS, mekonyum aspirasyonu [KG Context]"

Score: 5.0 - Perfect medical accuracy, entity coverage, KG enrichment
```

### Example 2: Good Answer (4.0)
```
Query: "Prematüre komplikasyonları nelerdir?"
Answer: "Prematüre bebeklerde sık görülen komplikasyonlar:
- RDS (Respiratuvar distres sendromu)
- Apne epizodları
- IVH (İntraventriküler kanama)
- NEC (Nekrotizan enterokolit) [Source 1]"

Score: 4.0 - Good coverage but lacks depth, could add more KG connections
```

### Example 3: Fair Answer (3.0)
```
Query: "Yenidoğan sepsisi nasıl tedavi edilir?"
Answer: "Sepsis treatment includes antibiotics and supportive care [Source 1]."

Score: 3.0 - Wrong language, lacks detail, no Turkish medical terminology
```

---

**Use this rubric to evaluate your GraphRAG system performance!** 📊
