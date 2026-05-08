# GraphRAG Architecture Documentation

## System Overview

This is a high-production GraphRAG (Knowledge Graph + RAG) system optimized for Arabic legal documents with multilingual support.

## Architecture Components

### 1. Core Architecture (GraphRAG & Scalability)

#### Graph Construction
- **Neo4j Knowledge Graph**: Stores entities and relationships
- **Entity Types**: Laws, Articles, Ministries, Organizations, Dates
- **Relationship Types**: REPEALS, AMENDS, REFERENCES, ISSUED_BY, APPLIES_TO
- **Extraction**: Regex-based pattern matching for Arabic legal text

#### Vector-Graph Hybrid Approach
- **Vector Store**: FAISS with OpenAI embeddings (text-embedding-3-large)
- **Graph Store**: Neo4j for relationship traversal
- **Fusion**: Reciprocal Rank Fusion (RRF) combines both results

#### Scalability
- **Async Processing**: Celery for background tasks
- **Connection Pooling**: Redis and Neo4j connection management
- **Batch Processing**: Efficient document ingestion

#### Semantic Caching
- **Redis Cache**: Stores query embeddings and responses
- **Similarity Matching**: Cosine similarity with 0.95 threshold
- **TTL**: 24-hour cache expiration
- **Cost Reduction**: Reduces LLM API calls by ~40-60%

### 2. Multilingual Logic & Darija Handling

#### Language Detection
- **Supported Languages**: Arabic, English, French, Darija
- **Detection Method**: langdetect + custom Darija patterns
- **Darija Patterns**: Regex matching for Moroccan dialect

#### Response Routing
```
Input Language → Response Language
Arabic         → Arabic
English        → English
French         → French
Darija         → Standard Arabic (for formal accuracy)
```

#### Cross-Lingual Retrieval
- **Multilingual Embeddings**: text-embedding-3-large supports 100+ languages
- **Query Translation**: Implicit through embedding space
- **Example**: French query → retrieves Arabic legal context

### 3. Guardrails & Safety

#### Domain Constraints
- **System Prompts**: Enforce legal domain focus
- **Verification**: Check for legal keywords in queries
- **Rejection**: Off-topic queries are politely declined

#### Political Neutrality
- **Filtering Layer**: Detects political topics, protests, sensitive content
- **Keyword Lists**: Maintained per language
- **Automatic Rejection**: Returns appropriate message

#### Hallucination Prevention
- **Citation Requirement**: Every answer must cite Law/Article number
- **Context-Only**: LLM instructed to use only provided context
- **Validation**: Post-generation citation check

### 4. Technical Stack

#### LangGraph Workflow
```
detect_language → check_safety → check_cache → retrieve_documents → 
generate_answer → validate_citations → cache_response
```

#### Pydantic Models
- **Type Safety**: All data structures validated
- **Structured Output**: Consistent API responses
- **Configuration**: Settings management

#### Reciprocal Rank Fusion (RRF)
```python
score(document) = Σ 1 / (k + rank(document))
where k = 60 (constant)
```

Combines:
- Vector search results (semantic similarity)
- Graph traversal results (relationship-based)

## Data Flow

```
User Query
    ↓
Language Detection (Darija → Arabic)
    ↓
Safety Check (Political filter, Domain check)
    ↓
Semantic Cache Check (Redis)
    ↓ (if miss)
Hybrid Retrieval:
    ├─ Vector Search (FAISS)
    └─ Graph Traversal (Neo4j)
    ↓
RRF Fusion
    ↓
LLM Generation (GPT-4 with guardrails)
    ↓
Citation Validation
    ↓
Cache Response (Redis)
    ↓
Return to User
```

## Performance Optimizations

### Caching Strategy
- **Semantic Cache**: 95% similarity threshold
- **Exact Match**: Hash-based lookup
- **Hit Rate**: ~40-60% for common queries

### Retrieval Optimization
- **RRF**: Combines multiple ranking signals
- **Top-K**: Retrieve 10 from each source, return 5 fused
- **Graph Depth**: Max 2 hops for relationship traversal

### Embedding Optimization
- **Model**: text-embedding-3-large (3072 dimensions)
- **Batch Processing**: Embed multiple documents together
- **Normalization**: Arabic text normalization before embedding

## Deployment Architecture

```
┌─────────────────┐
│   FastAPI App   │
│   (Port 8000)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────┐
│ Redis │ │  Neo4j  │
│ Cache │ │  Graph  │
└───────┘ └─────────┘
```

## Security Considerations

1. **API Key Management**: Environment variables only
2. **Input Validation**: Pydantic models + length limits
3. **Rate Limiting**: Can be added via FastAPI middleware
4. **Content Filtering**: Political and violent content blocked
5. **Citation Requirements**: Prevents hallucination

## Monitoring & Logging

- **Structured Logging**: JSON format with timestamps
- **Metrics**: Processing time, cache hit rate, retrieval method
- **Health Checks**: Redis, Neo4j, LLM connectivity
- **Error Tracking**: Comprehensive exception handling

## Future Enhancements

1. **Advanced NER**: Use Arabic NER models (CAMeL Tools)
2. **Query Expansion**: Synonym expansion for Arabic
3. **Multi-hop Reasoning**: Complex graph queries
4. **Fine-tuned Embeddings**: Domain-specific Arabic embeddings
5. **Real-time Updates**: Streaming document ingestion
