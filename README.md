# SPIRAL-RAG v3 — Multilingual Legal RAG for Algerian Higher Education Regulations

**Self-reflective Parallel Iterative Retrieval with Adaptive Language**

A research-grade Retrieval-Augmented Generation system designed specifically for the regulatory corpus of the Algerian Ministry of Higher Education and Scientific Research (2018–2024). The system answers questions in Arabic, French, English, and Algerian Darija (Arabic-script variant supported) with inline citations to source documents.

---

## What this system does

SPIRAL-RAG v3 retrieves and synthesises answers from 8,622 document chunks spanning seven years of ministerial decrees, circulars, and Official Gazette publications. It is not a general-purpose chatbot — every response is grounded in retrieved regulatory text and includes explicit source references (year, title, authority tier).

The architecture introduces five novel components over a standard RAG pipeline:

- **Query Intent Routing** — classifies each query into one of four intents (Definitional, Procedural, Temporal, Comparative) and adjusts retrieval weight coefficients accordingly, yielding +2.8% Context Precision over a fixed-weight baseline.
- **Semantic Authority Classification** — a SetFit zero-shot classifier assigns authority tier (Official Gazette / Decree / Circular) from document-title embeddings only, reducing false-positive rate from 44% to 29% compared to full-text regex.
- **Temporal Supersession Detection** — cosine similarity across title embeddings identifies newer documents that may override older ones; confirmed supersessions surface as alerts in the UI.
- **Multi-Agent Legal Debate (MALD)** — an Advocate and Devil's Advocate (Groq Llama-3.3-70b) argue interpretations of retrieved evidence; a Judge (Gemini 2.0 Flash) synthesises the final answer, making interpretive uncertainty explicit rather than hidden.
- **Token Cost Tracking** — every API call is metered at token level; per-query cost is returned alongside the answer.

---

## Evaluation results

Evaluated on a 330-question multilingual benchmark (80 Factual, 63 Temporal, 42 Comparative, 45 Procedural, 50 Darija) using RAGAS metrics, with partial human annotation on 50 questions (Fleiss κ = 0.61):

| System | Faithfulness | Ans. Relevance | Ctx Precision | Ctx Recall |
|---|---|---|---|---|
| Naive RAG baseline | 0.580 | 0.761 | 0.662 | 0.709 |
| SPIRAL-RAG v2 | 0.831 | 0.874 | 0.782 | 0.789 |
| **SPIRAL-RAG v3** | **0.856** | **0.891** | **0.808** | **0.814** |

Average per-query API cost: $0.0042 USD. Marginal cost per +1% Faithfulness gain over v2: $0.0024.

---

## Repository structure

```
Ministry-Regulation/
├── Rag/
│   ├── app.py                   Flask API server (port 5000)
│   ├── rag_core.py              SPIRAL-RAG engine (all five innovations)
│   ├── index.html               Landing page
│   └── chat.html                Chat interface
│
├── data/                        Legal corpus (JSON, by year)
│   ├── 2018/ … 2024/
│
├── evaluation/
│   ├── generate_benchmark.py    Benchmark generation script
│   └── benchmark.csv            330-question evaluation set
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DEPLOYMENT.md
│   └── EVALUATION_GUIDE.md
│
├── SPIRAL_RAG_v3_Research_Paper.tex    Research paper (LaTeX source)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Setup

Requires Python 3.10+. Two API keys are needed: [Groq](https://console.groq.com) (Llama-3.3-70b reasoning) and [Google Gemini](https://aistudio.google.com) (embeddings + synthesis).

```bash
git clone https://github.com/Samir-Guenchi/Ministry-Regulation.git
cd Ministry-Regulation
pip install -r requirements.txt
cp .env.example .env
# Add GROQ_API_KEY and GEMINI_API_KEY to .env
cd Rag
python app.py
```

The server starts on `http://localhost:5000`. First startup takes 30–60 seconds while 8,622 chunks are indexed and embedding cache is loaded from disk.

### Docker

```bash
docker-compose up -d
```

---

## API reference

### POST /api/ask

```json
{ "question": "ما هي شروط التسجيل في الدكتوراه؟" }
```

Response includes: `answer`, `citations` (year, title, authority tier, relevance score), `confidence`, `intent_label`, `debate_summary`, `supersession_alerts`, `cost_estimate`, `reflection_log`, `processing_time_ms`.

### GET /api/stats

Returns corpus size, model identifiers, architecture version, language support.

### GET /api/health

System readiness and chunk count.

Full reference: [docs/API.md](docs/API.md)

---

## Architecture notes

**Retrieval.** BM25 (lexical) and Gemini `text-embedding-004` dense retrieval run in parallel across query expansion variants. Results fused with Reciprocal Rank Fusion (k=60). A multilingual cross-encoder (`mmarco-mMiniLMv2-L6-H384-v1` or `BGE-M3`) re-ranks top candidates before context passes to the debate agents.

**Language detection.** Arabic / French / English via langdetect. Algerian Darija detected via a 47-word Arabic-script lexicon with Levenshtein distance ≤ 2 fuzzy matching to handle non-standardised spelling.

**MALD context.** Top-3 re-ranked chunks go to the debate agents; the full retrieved set remains available to the Judge for citation lookup. Debate context is reduced by 62% versus passing all chunks.

**Temporal weighting.** Publication year used as recency proxy. Effective-date parsing (distinguishing publication date from in-force date) is identified as a known limitation and planned for v4.

---

## Known limitations

The research paper (Section 6) documents eight limitations in full. The most critical for deployment:

1. **Parametric memory contamination** — cannot exclude that Gemini/Llama pre-training data included Official Gazette text; Context Precision/Recall metrics partially mitigate this.
2. **Binary supersession** — the detector cannot distinguish partial amendment (one article changed) from total replacement; article-level segmentation is needed.
3. **Unverified citation hallucination** — `[REF-N]` citations are not programmatically checked against chunk text; a post-generation fuzzy verifier is planned.
4. **Cross-encoder token truncation** — chunks over 512 tokens are silently cut; a long-context reranker is the planned fix.

---

## Research paper

`SPIRAL_RAG_v3_Research_Paper.tex` documents the full architecture, ablation study, 330-question benchmark, and responses to 22 peer-review concerns. Compile with:

```bash
pdflatex SPIRAL_RAG_v3_Research_Paper.tex
bibtex SPIRAL_RAG_v3_Research_Paper
pdflatex SPIRAL_RAG_v3_Research_Paper.tex
pdflatex SPIRAL_RAG_v3_Research_Paper.tex
```

---

## Licence

MIT — see [LICENSE](LICENSE).

## Contact

Samir Guenchi · samir.guenchi@ensia.edu.dz · ENSIA, Algeria
