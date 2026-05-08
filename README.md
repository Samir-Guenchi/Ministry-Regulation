# SPIRAL-RAG: Ministry Regulation Q&A System

**Self-reflective Parallel Iterative Retrieval with Adaptive Language**

[![Version](https://img.shields.io/badge/version-2.0-blue.svg)](https://github.com/Samir-Guenchi/Ministry-Regulation)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

---

## 📋 Overview

An advanced multilingual RAG system for Algerian Ministry of Higher Education regulations. SPIRAL-RAG combines dense retrieval, legal authority scoring, and adaptive reasoning to provide accurate, cited answers in Arabic, French, English, and Algerian Darija.

### **Key Features**

✅ **Dense Retrieval** - Gemini text-embedding-004 (768-dim multilingual embeddings)  
✅ **Legal Authority Scoring** - Prioritizes Official Gazette, Decrees, and Circulars  
✅ **Adaptive Confidence Threshold** - Score-distribution driven (not hardcoded)  
✅ **Parallel Processing** - Concurrent LLM calls reduce latency  
✅ **Multilingual Support** - Arabic, French, English, Darija  
✅ **Self-Reflective Retrieval** - Iterative refinement with relevance scoring  

---

## 🚀 Quick Start

### **1. Installation**

```bash
# Clone repository
git clone https://github.com/Samir-Guenchi/Ministry-Regulation.git
cd Ministry-Regulation

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your API keys
```

### **2. Configuration**

Edit `.env` file:
```bash
# Required API Keys
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Data Configuration
DATA_DIRECTORY=./data

# Optional Settings
CACHE_DIRECTORY=./cache
LOG_LEVEL=INFO
```

### **3. Start System**

```bash
# Navigate to Rag directory
cd Rag

# Start Flask server
python app.py

# API available at: http://localhost:5000
```

### **4. Query Example**

```bash
curl -X POST "http://localhost:5000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ما هي شروط التسجيل في الدكتوراه؟",
    "language": "ar"
  }'
```

---

## 📁 Project Structure

```
Ministry-Regulation/
├── Rag/                          # SPIRAL-RAG application
│   ├── app.py                   # Flask API server
│   ├── rag_core.py              # Core SPIRAL-RAG engine
│   ├── index.html               # Landing page
│   ├── chat.html                # Chat interface
│   ├── ai.jpg                   # UI assets
│   └── logo.png
│
├── data/                         # Legal documents (JSON)
│   ├── 2018/
│   ├── 2019/
│   ├── 2020/
│   ├── 2021/
│   ├── 2022/
│   ├── 2023/
│   └── 2024/
│
├── evaluation/                   # Evaluation framework
│   ├── generate_benchmark.py   # Benchmark generator
│   └── benchmark.csv            # 300+ evaluation questions
│
├── docs/                         # Documentation
│   ├── API.md                   # API reference
│   ├── ARCHITECTURE.md          # System architecture
│   ├── DEPLOYMENT.md            # Deployment guide
│   ├── EVALUATION_GUIDE.md      # Evaluation metrics
│   ├── QUICK_START_ENHANCED.md  # Quick reference
│   ├── RAG_SYSTEM_LATEX.pdf     # Research paper (PDF)
│   ├── RAG_SYSTEM_LATEX.tex     # Research paper (LaTeX)
│   └── RAG_SYSTEM_PRESENTATION.tex # Presentation slides
│
├── SPIRAL_RAG_Research_Paper.tex # Main research paper
├── SPIRAL_RAG_Paper.zip         # Paper archive
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Docker setup
├── Dockerfile                   # Docker image
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

---

## 🎯 System Architecture

### **SPIRAL-RAG Pipeline**

```
User Query
    ↓
1. Language Detection (Arabic/French/English/Darija)
    ↓
2. Query Expansion (Groq - 3 variants)
    ↓
3. Hybrid Retrieval (Parallel)
    ├─→ BM25 (lexical)
    └─→ Dense Embeddings (Gemini)
    ↓
4. Reciprocal Rank Fusion (RRF)
    ↓
5. Self-Reflective Scoring (Groq)
    ├─→ Relevance judgment
    ├─→ Adaptive threshold
    └─→ Iterate if needed (max 3)
    ↓
6. Legal Authority Ranking
    ├─→ Official Gazette (1.0)
    ├─→ Decree (0.75)
    └─→ Circular (0.50)
    ↓
7. Synthesis (Gemini 2.0 Flash)
    ↓
8. Validation (Groq consistency check)
    ↓
Final Answer with Citations
```

### **Key Innovations**

#### **[R1] Dense Retrieval**
- **Replaces**: Sparse TF-IDF
- **Uses**: Gemini text-embedding-004 (768-dim)
- **Benefits**: Handles Arabic morphology, paraphrasing, cross-lingual queries
- **Caching**: Disk-based for O(1) warm-start

#### **[R2] Legal Authority Scoring**
- **Replaces**: Multi-year triangulation (legally flawed)
- **Hierarchy**: Official Gazette > Decree > Circular
- **Principle**: Single authoritative source is valid

#### **[R3] Adaptive Confidence Threshold**
- **Replaces**: Fixed 0.65 threshold
- **Formula**: `median + 0.5 * IQR` of relevance scores
- **Range**: [0.45, 0.80]

#### **[R4] Parallel Processing**
- **ThreadPoolExecutor** for concurrent API calls
- **Reduces**: Tail latency under load
- **Parallelizes**: Query expansion, retrieval, scoring

---

## 🔧 API Reference

### **POST /api/ask**

Query the SPIRAL-RAG system.

**Request:**
```json
{
  "question": "ما هي شروط التسجيل في الدكتوراه؟",
  "language": "ar"  // optional: ar, fr, en, dz
}
```

**Response:**
```json
{
  "answer": "Complete answer with inline citations [REF-1]...",
  "language": "ar",
  "language_name": "Arabic",
  "confidence": 0.85,
  "citations": [
    {
      "ref": "REF-1",
      "year": "2023",
      "title": "منشور رقم 123",
      "file": "2023_1.json",
      "authority_tier": 2,
      "authority_label": "Ministerial Decree",
      "relevance": 0.92,
      "dense_score": 0.847
    }
  ],
  "evidence_count": 12,
  "iterations": 2,
  "reflection_log": [
    "Language detected: Arabic",
    "Query expanded to 4 variants",
    "Iter 1: +15 chunks | conf=0.68 | adaptive_thresh=0.65",
    "Iter 2: +8 chunks | conf=0.85 | adaptive_thresh=0.72",
    "Adaptive threshold met — stopping at iteration 2"
  ],
  "processing_time_ms": 2847.3
}
```

### **GET /api/stats**

Get system statistics.

**Response:**
```json
{
  "total_chunks": 3247,
  "by_year": {
    "2018": 412,
    "2019": 389,
    "2020": 456,
    "2021": 501,
    "2022": 487,
    "2023": 523,
    "2024": 479
  },
  "architecture": "SPIRAL-RAG",
  "llms": {
    "reasoning": "Groq llama-3.3-70b-versatile",
    "synthesis": "Google Gemini 2.0 Flash",
    "embedding": "Gemini Embedding-001 (dense, 768-dim)"
  },
  "languages_supported": ["Arabic", "French", "English", "Algerian Darija"],
  "max_iterations": 3,
  "confidence_threshold": "adaptive (IQR-based, per query)",
  "retrieval": "BM25 + Gemini Dense Embeddings via RRF",
  "version": "v2"
}
```

### **GET /api/health**

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "groq_configured": true,
  "gemini_configured": true,
  "corpus_loaded": true,
  "chunk_count": 3247
}
```

---

## 📊 Evaluation

### **Benchmark Dataset**

The system includes a comprehensive evaluation framework:

- **300+ questions** across 6 types:
  - Factual (~80)
  - Temporal (~63)
  - Comparative (~42)
  - Procedural (~45)
  - Eligibility (~30)
  - Darija (~50)

- **4 languages**: Arabic, French, English, Darija

### **Generate Benchmark**

```bash
cd evaluation
python generate_benchmark.py --output benchmark.csv
```

### **Evaluation Metrics**

- **Faithfulness**: Answer grounded in retrieved evidence
- **Answer Relevance**: Directly addresses the question
- **Context Precision**: Relevant chunks ranked highly
- **Context Recall**: All relevant information retrieved

---

## 🐳 Docker Deployment

```bash
# Build and start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f rag-api

# Stop
docker-compose down
```

---

## 🔒 Security & Safety

- ✅ **API Key Management** - Environment variables only
- ✅ **Input Validation** - Length limits, sanitization
- ✅ **Political Content Filtering** - Blocks sensitive topics
- ✅ **Violent Content Detection** - Safety guardrails
- ✅ **Citation Requirements** - Prevents hallucination
- ✅ **Consistency Validation** - Groq-based fact checking

---

## 🌍 Multilingual Support

| Language | Detection | Query | Response | Status |
|----------|-----------|-------|----------|--------|
| **Arabic** | ✅ | ✅ | ✅ | Full support |
| **French** | ✅ | ✅ | ✅ | Full support |
| **English** | ✅ | ✅ | ✅ | Full support |
| **Darija** | ✅ | ✅ | ✅ | Full support |

---

## 📈 Performance

| Metric | Value |
|--------|-------|
| **Average Latency** | 2.8s |
| **Cache Hit Rate** | 40-60% |
| **Embedding Dimension** | 768 |
| **Max Iterations** | 3 |
| **Top-K Results** | 8 |
| **Corpus Size** | 3,000+ chunks |

---

## 📚 Documentation

- **[API Reference](docs/API.md)** - Complete API documentation
- **[Architecture](docs/ARCHITECTURE.md)** - System design
- **[Deployment](docs/DEPLOYMENT.md)** - Production deployment
- **[Evaluation](docs/EVALUATION_GUIDE.md)** - Metrics and benchmarks
- **[Quick Start](docs/QUICK_START_ENHANCED.md)** - Quick reference

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 🙏 Acknowledgments

- **Groq** - Fast LLM inference (llama-3.3-70b-versatile)
- **Google Gemini** - Embeddings and synthesis
- **LangDetect** - Language detection
- **NumPy** - Vector operations
- **Flask** - Web framework

---

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/Samir-Guenchi/Ministry-Regulation/issues)
- **Email**: samir.guenchi@ensia.edu.dz

---

**Built for the Algerian Ministry of Higher Education**

**Version 2.0** | **May 2026**
