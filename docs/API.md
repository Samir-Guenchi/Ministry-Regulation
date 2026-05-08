# API Reference

Complete API documentation for the Ministry Regulation GraphRAG system.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication required. For production, add API key authentication.

## Endpoints

### 1. Root Endpoint

**GET** `/`

Returns basic service information.

**Response:**
```json
{
  "service": "Ministry Regulation GraphRAG API",
  "version": "2.0.0",
  "status": "running"
}
```

---

### 2. Health Check

**GET** `/health`

Check system health and component status.

**Response:**
```json
{
  "status": "healthy",
  "cache": {
    "connected": true,
    "stats": {
      "total_keys": 1523,
      "memory_used_mb": 45.2,
      "hit_rate": 0.58
    }
  },
  "workflow": "initialized"
}
```

**Status Codes:**
- `200`: System healthy
- `503`: System unhealthy

---

### 3. Query Legal Questions

**POST** `/query`

Process legal questions with multilingual support.

**Request Body:**
```json
{
  "question": "ما هي شروط التوظيف في الوزارة؟",
  "language": "ar",  // Optional: ar, en, fr, darija
  "include_graph": true,  // Optional, default: true
  "max_results": 5,  // Optional, default: 5, range: 1-20
  "year_filter": ["2022", "2023"]  // Optional
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| question | string | Yes | - | User question (max 500 chars) |
| language | string | No | auto-detect | Language code: ar, en, fr, darija |
| include_graph | boolean | No | true | Include graph traversal |
| max_results | integer | No | 5 | Max results (1-20) |
| year_filter | array | No | null | Filter by years |

**Response:**
```json
{
  "answer": "بناءً على القانون رقم 12.20، شروط التوظيف هي...",
  "detected_language": "ar",
  "response_language": "ar",
  "citations": [
    {
      "law_name": "قانون رقم 12.20",
      "article_number": "5",
      "year": "2020",
      "text_excerpt": "يشترط في المترشح أن يكون...",
      "confidence": 0.92,
      "source_file": "2020_1.json"
    }
  ],
  "graph_entities": [
    {
      "entity_id": "law_2020_12_20",
      "entity_type": "Law",
      "name": "قانون رقم 12.20",
      "properties": {
        "law_type": "قانون",
        "law_number": "12.20",
        "year": "2020"
      }
    }
  ],
  "graph_relationships": [
    {
      "source_id": "law_2020_12_20",
      "target_id": "law_2018_10_15",
      "relationship_type": "AMENDS",
      "properties": {
        "context": "يعدل القانون رقم 10.15"
      }
    }
  ],
  "cached": false,
  "processing_time_ms": 1250.5,
  "retrieval_method": "hybrid"
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid request (question too short, invalid parameters)
- `500`: Server error

**Examples:**

```bash
# Arabic query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "ما هي شروط التوظيف؟"}'

# English query
curl -X POST http://localhost:8000/query \
  -d '{"question": "What are the employment requirements?"}'

# Darija query (responds in Standard Arabic)
curl -X POST http://localhost:8000/query \
  -d '{"question": "واش كاين شي شروط للخدمة؟"}'

# With filters
curl -X POST http://localhost:8000/query \
  -d '{
    "question": "ما هي القوانين الجديدة؟",
    "year_filter": ["2023", "2024"],
    "max_results": 10
  }'
```

---

### 4. Document Ingestion

**POST** `/ingest`

Upload and process legal documents.

**Request:**
- Content-Type: `multipart/form-data`
- File: PDF document

**Response:**
```json
{
  "task_id": "task_abc123",
  "status": "queued",
  "message": "Document queued for processing",
  "documents_processed": 0
}
```

**Status Codes:**
- `200`: Document queued
- `400`: Invalid file
- `500`: Processing error

**Example:**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf"
```

---

### 5. Cache Statistics

**GET** `/cache/stats`

Get semantic cache statistics.

**Response:**
```json
{
  "total_keys": 1523,
  "memory_used_mb": 45.2,
  "hit_rate": 0.58,
  "connected_clients": 3
}
```

**Example:**
```bash
curl http://localhost:8000/cache/stats
```

---

### 6. Invalidate Cache

**POST** `/cache/invalidate`

Clear all cache entries.

**Response:**
```json
{
  "message": "Invalidated 1523 cache entries"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/cache/invalidate
```

---

## Response Models

### QueryResponse

```typescript
{
  answer: string;
  detected_language: "ar" | "en" | "fr" | "darija";
  response_language: "ar" | "en" | "fr";
  citations: Citation[];
  graph_entities?: GraphEntity[];
  graph_relationships?: GraphRelationship[];
  cached: boolean;
  processing_time_ms: number;
  retrieval_method: "vector" | "graph" | "hybrid";
}
```

### Citation

```typescript
{
  law_name: string;
  article_number?: string;
  year: string;
  text_excerpt: string;
  confidence: number;  // 0.0 - 1.0
  source_file?: string;
}
```

### GraphEntity

```typescript
{
  entity_id: string;
  entity_type: "Law" | "Article" | "Ministry" | "Organization" | "Date";
  name: string;
  properties: Record<string, any>;
}
```

### GraphRelationship

```typescript
{
  source_id: string;
  target_id: string;
  relationship_type: "REPEALS" | "AMENDS" | "REFERENCES" | "ISSUED_BY" | "APPLIES_TO";
  properties: Record<string, any>;
}
```

---

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Question too short or empty"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Error processing query: [error message]"
}
```

### 503 Service Unavailable

```json
{
  "status": "unhealthy",
  "error": "Redis connection failed"
}
```

---

## Language Support

### Supported Languages

| Code | Language | Notes |
|------|----------|-------|
| `ar` | Arabic | Standard Arabic |
| `en` | English | - |
| `fr` | French | - |
| `darija` | Darija | Moroccan Arabic dialect |

### Language Detection

The system automatically detects the input language. You can optionally specify it:

```json
{
  "question": "What are the requirements?",
  "language": "en"
}
```

### Darija Handling

Darija queries are automatically detected and responded to in Standard Arabic for formal accuracy:

**Input (Darija):**
```json
{
  "question": "واش كاين شي شروط للخدمة؟"
}
```

**Response:**
```json
{
  "detected_language": "darija",
  "response_language": "ar",
  "answer": "بناءً على القانون..."
}
```

---

## Safety & Guardrails

### Political Content

Political queries are automatically rejected:

**Request:**
```json
{
  "question": "ما رأيك في الحكومة؟"
}
```

**Response:**
```json
{
  "answer": "نعتذر، لا يمكننا معالجة الأسئلة المتعلقة بالمواضيع السياسية الحساسة...",
  "detected_language": "ar",
  "response_language": "ar",
  "citations": [],
  "cached": false,
  "processing_time_ms": 50.2,
  "retrieval_method": "none"
}
```

### Off-Topic Queries

Non-legal queries are politely declined:

**Request:**
```json
{
  "question": "What is the weather today?"
}
```

**Response:**
```json
{
  "answer": "Your question doesn't seem to be related to laws and ministry regulations...",
  ...
}
```

---

## Rate Limiting

Currently no rate limiting. For production, implement:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/query")
@limiter.limit("10/minute")
async def query(request: QueryRequest):
    ...
```

---

## Caching Behavior

### Cache Hit

When a semantically similar query is found in cache:

```json
{
  "cached": true,
  "cache_type": "semantic",
  "similarity_score": 0.97,
  "processing_time_ms": 45.2
}
```

### Cache Miss

When no similar query is found:

```json
{
  "cached": false,
  "processing_time_ms": 1250.5
}
```

### Cache Threshold

Similarity threshold: **0.95** (configurable in `.env`)

---

## Interactive API Documentation

FastAPI provides interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These interfaces allow you to:
- Test endpoints directly
- View request/response schemas
- See example requests
- Download OpenAPI spec

---

## Client Libraries

### Python

```python
import requests

class MinistryRegulationClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def query(self, question: str, **kwargs):
        response = requests.post(
            f"{self.base_url}/query",
            json={"question": question, **kwargs}
        )
        return response.json()
    
    def health(self):
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def cache_stats(self):
        response = requests.get(f"{self.base_url}/cache/stats")
        return response.json()

# Usage
client = MinistryRegulationClient()
result = client.query("ما هي شروط التوظيف؟")
print(result["answer"])
```

### JavaScript/TypeScript

```typescript
class MinistryRegulationClient {
  constructor(private baseUrl = "http://localhost:8000") {}
  
  async query(question: string, options = {}) {
    const response = await fetch(`${this.baseUrl}/query`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question, ...options})
    });
    return await response.json();
  }
  
  async health() {
    const response = await fetch(`${this.baseUrl}/health`);
    return await response.json();
  }
  
  async cacheStats() {
    const response = await fetch(`${this.baseUrl}/cache/stats`);
    return await response.json();
  }
}

// Usage
const client = new MinistryRegulationClient();
const result = await client.query("ما هي شروط التوظيف؟");
console.log(result.answer);
```

---

## WebSocket Support (Future)

For real-time streaming responses:

```python
@app.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    await websocket.accept()
    while True:
        question = await websocket.receive_text()
        # Stream response chunks
        async for chunk in stream_answer(question):
            await websocket.send_text(chunk)
```

---

## Monitoring & Metrics

### Prometheus Metrics (Future)

```python
from prometheus_client import Counter, Histogram

query_counter = Counter('queries_total', 'Total queries')
query_duration = Histogram('query_duration_seconds', 'Query duration')
cache_hits = Counter('cache_hits_total', 'Cache hits')
```

### Health Check Monitoring

```bash
# Monitor health endpoint
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

---

## Best Practices

1. **Always check health** before making queries
2. **Use caching** for frequently asked questions
3. **Specify language** when known for faster processing
4. **Filter by year** for more relevant results
5. **Handle errors** gracefully in client code
6. **Monitor cache hit rate** for optimization
7. **Respect rate limits** in production

---

## Support

- **API Issues**: [GitHub Issues](https://github.com/Samir-Guenchi/Ministry-Regulation/issues)
- **Documentation**: See [README_GRAPHRAG.md](README_GRAPHRAG.md)
- **Interactive Docs**: http://localhost:8000/docs
