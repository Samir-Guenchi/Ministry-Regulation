from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """GraphRAG System Configuration"""
    
    # Groq API Configuration
    groq_api_key: str = "your_groq_api_key_here"
    groq_model: str = "llama-3.3-70b-versatile"
    
    # OpenAI (for embeddings only)
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-large"
    
    # Data Source
    data_directory: str = r"C:\Users\Samir Guenchi\Desktop\RAG\Ministry-Regulation\data"
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "your_password"
    
    # Redis (Optional - using local cache instead)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    use_redis: bool = False  # Set to False to use local FAISS cache
    
    # Application
    environment: str = "production"
    log_level: str = "INFO"
    max_workers: int = 4
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Semantic Cache Configuration
    cache_directory: str = "./cache"
    cache_ttl: int = 86400
    similarity_threshold: float = 0.90  # Threshold for semantic cache matching
    
    # Guardrails
    enable_political_filter: bool = True
    require_citations: bool = True
    max_query_length: int = 500
    block_out_of_scope: bool = True
    
    # JSON Output Enforcement
    force_json_output: bool = True
    
    # Google Gemini (Fallback)
    google_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
