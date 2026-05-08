# RAG Evaluation Guide

## Overview

This guide explains how to evaluate the GraphRAG system using standard RAG metrics.

## Evaluation Metrics

### 1. **Faithfulness** (0-1)
Measures if the answer is grounded in the retrieved context.
- **1.0**: All statements in answer are supported by context
- **0.0**: No statements are supported by context

### 2. **Answer Relevancy** (0-1)
Measures if the answer addresses the question.
- **1.0**: Answer directly and completely addresses question
- **0.0**: Answer is completely irrelevant

### 3. **Context Relevancy** (0-1)
Measures if retrieved contexts are relevant to the question.
- **1.0**: All retrieved contexts are relevant
- **0.0**: No contexts are relevant

### 4. **Context Precision** (0-1)
Measures if relevant contexts are ranked higher.
- **1.0**: All top-ranked contexts are relevant
- **0.0**: No top-ranked contexts are relevant

### 5. **Context Recall** (0-1)
Measures if all relevant information was retrieved.
- **1.0**: All necessary information was retrieved
- **0.0**: No relevant information was retrieved

### 6. **Overall Score** (0-1)
Average of all five metrics.

---

## Running Evaluation

### Prerequisites

1. **System Running**:
```bash
python start_system.py
```

2. **Documents Loaded**:
Ensure legal documents are in the data directory.

### Run Evaluation

```bash
python run_evaluation.py
```

### Expected Output

```
============================================================
Ministry Regulation RAG System - Evaluation Suite
============================================================

✓ API is running

============================================================
Cache Effectiveness Test
============================================================

1. First query (should be uncached)...
   Time: 1250.50ms
   Cached: False

2. Second query (should be cached)...
   Time: 45.20ms
   Cached: True

3. Similar query (should be cached)...
   Time: 42.80ms
   Cached: True
   Similarity: 0.96

✓ Cache speedup: 27.7x faster

============================================================
RAG System Evaluation
============================================================

[1/5] Testing: ما هي شروط التوظيف في الوزارة؟...
  Language: ar → ar
  Cached: False
  Time: 1250.50ms
  Citations: 3

  RAG Evaluation Scores:
    Faithfulness:       0.850
    Answer Relevancy:   0.900
    Context Relevancy:  0.800
    Context Precision:  0.900
    Context Recall:     0.750
    Overall Score:      0.840

[2/5] Testing: What are the employment requirements?...
  Language: en → en
  Cached: False
  Time: 1180.30ms
  Citations: 2

  RAG Evaluation Scores:
    Faithfulness:       0.800
    Answer Relevancy:   0.850
    Context Relevancy:  0.750
    Context Precision:  0.800
    Context Recall:     0.700
    Overall Score:      0.780

[3/5] Testing: Quelles sont les conditions d'emploi?...
  Language: fr → fr
  Cached: False
  Time: 1220.40ms
  Citations: 2

  RAG Evaluation Scores:
    Faithfulness:       0.820
    Answer Relevancy:   0.880
    Context Relevancy:  0.780
    Context Precision:  0.850
    Context Recall:     0.720
    Overall Score:      0.810

[4/5] Testing: واش كاين شي شروط للخدمة؟...
  Language: darija → ar
  Cached: False
  Time: 1190.20ms
  Citations: 3
  ✓ Darija → Arabic conversion working

  RAG Evaluation Scores:
    Faithfulness:       0.870
    Answer Relevancy:   0.920
    Context Relevancy:  0.830
    Context Precision:  0.880
    Context Recall:     0.780
    Overall Score:      0.856

[5/5] Testing: ما هي إجراءات التظلم؟...
  Language: ar → ar
  Cached: False
  Time: 1210.60ms
  Citations: 2

  RAG Evaluation Scores:
    Faithfulness:       0.790
    Answer Relevancy:   0.860
    Context Relevancy:  0.740
    Context Precision:  0.820
    Context Recall:     0.690
    Overall Score:      0.780

============================================================
Evaluation Summary
============================================================

Performance Metrics:
  Total Queries:        5
  Cached Queries:       0
  Cache Hit Rate:       0.0%
  Avg Processing Time:  1210.40ms
  Recent Avg Time:      1210.40ms

Language Distribution:
  ar: 3
  en: 1
  fr: 1
  darija: 1

RAG Quality Metrics (Average):
  Faithfulness:       0.826
  Answer Relevancy:   0.882
  Context Relevancy:  0.780
  Context Precision:  0.850
  Context Recall:     0.728
  Overall Score:      0.813

✓ Results saved to: ./metrics/evaluation_20260201_143022.json

============================================================

✓ Evaluation complete!

Next steps:
  1. Review metrics in ./metrics/ directory
  2. Check cache stats: curl http://localhost:8000/cache/stats
  3. Fine-tune similarity threshold if needed
```

---

## Interpreting Results

### Good Scores (>0.8)
- System is performing well
- Answers are grounded and relevant
- Context retrieval is effective

### Moderate Scores (0.6-0.8)
- System is functional but needs improvement
- Consider:
  - Adding more documents
  - Improving chunking strategy
  - Fine-tuning retrieval parameters

### Poor Scores (<0.6)
- System needs significant improvement
- Check:
  - Document quality
  - Embedding model
  - Retrieval algorithm
  - Prompt engineering

---

## Metrics Breakdown

### High Faithfulness + Low Context Recall
**Issue**: Retrieved contexts don't contain all necessary information.
**Solution**: 
- Increase number of retrieved documents
- Improve chunking strategy
- Add more comprehensive documents

### High Context Relevancy + Low Answer Relevancy
**Issue**: Good retrieval but poor answer generation.
**Solution**:
- Improve system prompts
- Fine-tune LLM parameters
- Add better examples

### Low Context Precision
**Issue**: Relevant contexts not ranked highly.
**Solution**:
- Improve ranking algorithm (RRF parameters)
- Fine-tune embedding model
- Add reranking step

---

## Performance Benchmarks

### Target Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Faithfulness | >0.85 | >0.70 |
| Answer Relevancy | >0.90 | >0.75 |
| Context Relevancy | >0.80 | >0.65 |
| Context Precision | >0.85 | >0.70 |
| Context Recall | >0.75 | >0.60 |
| Overall Score | >0.83 | >0.68 |

### Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| Response Time (uncached) | <1500ms | <2500ms |
| Response Time (cached) | <100ms | <200ms |
| Cache Hit Rate | >50% | >30% |
| Token Usage | <2000/query | <3000/query |

---

## Continuous Monitoring

### Real-time Monitoring

```bash
# Check system health
curl http://localhost:8000/health

# Check cache statistics
curl http://localhost:8000/cache/stats

# View performance report
curl http://localhost:8000/metrics/report
```

### Automated Evaluation

Run evaluation periodically:

```bash
# Daily evaluation
0 2 * * * cd /path/to/Ministry-Regulation && python run_evaluation.py

# Weekly comprehensive evaluation
0 3 * * 0 cd /path/to/Ministry-Regulation && python run_evaluation.py --comprehensive
```

---

## Improving Scores

### 1. Improve Faithfulness

**Add citation requirements:**
```python
# In workflow.py
system_prompt += "\nYou MUST cite specific law numbers and articles in your answer."
```

**Verify claims:**
```python
# Add post-processing to verify claims
if not self._verify_claims(answer, contexts):
    logger.warning("Answer contains unverified claims")
```

### 2. Improve Answer Relevancy

**Better prompts:**
```python
system_prompt = """You are a legal assistant. 
Answer ONLY the specific question asked.
Do not provide extra information."""
```

**Add relevancy check:**
```python
if not self._is_answer_relevant(question, answer):
    # Regenerate answer
    answer = self._regenerate_answer(question, contexts)
```

### 3. Improve Context Relevancy

**Better retrieval:**
```python
# Increase similarity threshold
similarity_threshold = 0.85

# Use hybrid search
use_graph = True
```

**Filter contexts:**
```python
# Remove irrelevant contexts before LLM
contexts = [c for c in contexts if self._is_relevant(c, question)]
```

### 4. Improve Context Precision

**Reranking:**
```python
# Add reranking step
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([(question, ctx) for ctx in contexts])
contexts = [ctx for _, ctx in sorted(zip(scores, contexts), reverse=True)]
```

**Adjust RRF:**
```python
# Fine-tune RRF constant
self.k = 40  # Lower k gives more weight to top results
```

### 5. Improve Context Recall

**Retrieve more documents:**
```python
max_results = 10  # Increase from 5
```

**Better chunking:**
```python
chunk_size = 1500  # Increase chunk size
chunk_overlap = 300  # Increase overlap
```

---

## Troubleshooting

### Low Scores Across All Metrics

**Check:**
1. Are documents loaded? `ls data/`
2. Is vector store built? `ls vector_store/`
3. Is API responding? `curl http://localhost:8000/health`

**Solution:**
```bash
# Rebuild indexes
python scripts/build_vector_store.py
python scripts/build_graph.py

# Restart system
python start_system.py
```

### Inconsistent Scores

**Issue**: Scores vary widely between queries.

**Solution:**
- Add more test cases
- Use ground truth answers
- Normalize evaluation criteria

### Evaluation Takes Too Long

**Issue**: Evaluation is slow.

**Solution:**
```python
# Reduce test cases
TEST_CASES = TEST_CASES[:3]

# Skip expensive metrics
skip_metrics = ['context_recall']

# Use faster model for evaluation
evaluation_model = "llama-3.1-8b-instant"
```

---

## Advanced Evaluation

### Custom Test Cases

Create `test_cases.json`:

```json
[
  {
    "question": "ما هي شروط التوظيف؟",
    "ground_truth": "الشروط هي...",
    "expected_citations": ["قانون 12.20", "المادة 5"]
  }
]
```

Run with custom cases:

```bash
python run_evaluation.py --test-cases test_cases.json
```

### A/B Testing

Compare different configurations:

```bash
# Test with different similarity thresholds
python run_evaluation.py --similarity-threshold 0.85
python run_evaluation.py --similarity-threshold 0.90
python run_evaluation.py --similarity-threshold 0.95

# Compare results
python compare_evaluations.py
```

---

## Reporting

### Generate Report

```bash
python run_evaluation.py --report
```

### View Metrics

```bash
# View latest evaluation
cat metrics/evaluation_*.json | jq '.rag_metrics'

# View performance trends
python analyze_metrics.py --trend
```

---

## Best Practices

1. **Run evaluation regularly** (daily/weekly)
2. **Track metrics over time** (use monitoring)
3. **Set quality thresholds** (fail if score < 0.7)
4. **Test edge cases** (Darija, long queries, etc.)
5. **Compare with baselines** (track improvements)
6. **Document changes** (link metrics to code changes)

---

## Next Steps

1. ✅ Run initial evaluation
2. ✅ Review metrics
3. ✅ Identify weak areas
4. ✅ Implement improvements
5. ✅ Re-evaluate
6. ✅ Deploy to production

---

**Evaluation system ready! 🎯**
