from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class Language(str, Enum):
    """Supported languages"""
    ARABIC = "ar"
    ENGLISH = "en"
    FRENCH = "fr"
    DARIJA = "darija"


class QueryRequest(BaseModel):
    """User query request"""
    question: str = Field(..., max_length=500)
    language: Optional[Language] = None
    include_graph: bool = True
    max_results: int = Field(default=5, ge=1, le=20)
    year_filter: Optional[List[str]] = None


class Citation(BaseModel):
    """Legal citation with source"""
    law_name: str
    article_number: Optional[str] = None
    year: str
    text_excerpt: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_file: Optional[str] = None


class GraphEntity(BaseModel):
    """Entity in knowledge graph"""
    entity_id: str
    entity_type: str  # Law, Article, Ministry, Date, Person, Organization
    name: str
    properties: Dict[str, Any] = {}


class GraphRelationship(BaseModel):
    """Relationship between entities"""
    source_id: str
    target_id: str
    relationship_type: str  # REPEALS, REFERENCES, AMENDS, ISSUED_BY, APPLIES_TO
    properties: Dict[str, Any] = {}


class QueryResponse(BaseModel):
    """Response to user query"""
    answer: str
    detected_language: Language
    response_language: Language
    citations: List[Citation]
    graph_entities: Optional[List[GraphEntity]] = None
    graph_relationships: Optional[List[GraphRelationship]] = None
    cached: bool = False
    processing_time_ms: float
    retrieval_method: str  # "vector", "graph", "hybrid"


class DocumentMetadata(BaseModel):
    """Metadata for legal documents"""
    document_id: str
    title: str
    year: str
    document_type: str = "regulation"
    publication_date: Optional[datetime] = None
    language: Language = Language.ARABIC
    source_file: str


class IngestRequest(BaseModel):
    """Document ingestion request"""
    file_path: str
    metadata: Optional[DocumentMetadata] = None
    build_graph: bool = True
    async_processing: bool = True


class IngestResponse(BaseModel):
    """Document ingestion response"""
    task_id: str
    status: str
    message: str
    documents_processed: int = 0
