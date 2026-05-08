"""
Semantic Cache Manager using FAISS for embedding-based similarity search
Optimized for token economy with Groq API
"""
import os
import json
import pickle
import hashlib
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import faiss
from langchain_openai import OpenAIEmbeddings
from graphrag.config import settings
import logging

logger = logging.getLogger(__name__)


class SemanticCacheManager:
    """
    FAISS-based semantic cache for query-response pairs
    
    Features:
    - Embedding-based similarity search
    - Configurable similarity threshold (default: 0.90)
    - TTL-based cache expiration
    - Persistent storage
    - Token economy optimization
    """
    
    def __init__(self):
        self.cache_dir = Path(settings.cache_directory)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embeddings
        if settings.openai_api_key:
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.openai_api_key
            )
        else:
            logger.warning("No OpenAI API key provided. Cache will use hash-based matching only.")
            self.embeddings = None
        
        # FAISS index
        self.index = None
        self.dimension = 3072  # text-embedding-3-large dimension
        
        # Cache metadata
        self.cache_metadata = {}  # Maps index_id -> metadata
        self.query_to_index = {}  # Maps query_hash -> index_id
        
        # Paths
        self.index_path = self.cache_dir / "faiss_index.bin"
        self.metadata_path = self.cache_dir / "cache_metadata.pkl"
        
        # Load existing cache
        self._load_cache()
        
        self.similarity_threshold = settings.similarity_threshold
        self.ttl = settings.cache_ttl
    
    def _load_cache(self):
        """Load existing FAISS index and metadata"""
        try:
            if self.index_path.exists() and self.metadata_path.exists():
                # Load FAISS index
                self.index = faiss.read_index(str(self.index_path))
                
                # Load metadata
                with open(self.metadata_path, 'rb') as f:
                    data = pickle.load(f)
                    self.cache_metadata = data.get('metadata', {})
                    self.query_to_index = data.get('query_to_index', {})
                
                logger.info(f"Loaded cache with {self.index.ntotal} entries")
            else:
                # Create new index
                self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
                logger.info("Created new FAISS index")
        
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            self.index = faiss.IndexFlatIP(self.dimension)
            self.cache_metadata = {}
            self.query_to_index = {}
    
    def _save_cache(self):
        """Persist FAISS index and metadata to disk"""
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_path))
            
            # Save metadata
            with open(self.metadata_path, 'wb') as f:
                pickle.dump({
                    'metadata': self.cache_metadata,
                    'query_to_index': self.query_to_index
                }, f)
            
            logger.debug("Cache saved successfully")
        
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def _generate_query_hash(self, query: str) -> str:
        """Generate hash for query"""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()
    
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector for cosine similarity"""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm
    
    def _is_expired(self, timestamp: str) -> bool:
        """Check if cache entry is expired"""
        try:
            cached_time = datetime.fromisoformat(timestamp)
            expiry_time = cached_time + timedelta(seconds=self.ttl)
            return datetime.now() > expiry_time
        except Exception:
            return True
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response for semantically similar query
        
        Args:
            query: User query text
            
        Returns:
            Cached response if found and similar enough (>0.90), None otherwise
        """
        if not self.embeddings:
            logger.warning("Embeddings not available, skipping cache lookup")
            return None
        
        try:
            # Check if index is empty
            if self.index.ntotal == 0:
                logger.debug("Cache is empty")
                return None
            
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            query_vector = np.array([query_embedding], dtype=np.float32)
            query_vector = self._normalize_vector(query_vector)
            
            # Search FAISS index
            k = min(5, self.index.ntotal)  # Search top 5 or all if less
            distances, indices = self.index.search(query_vector, k)
            
            # Check results
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:  # Invalid index
                    continue
                
                similarity = float(distance)  # Already cosine similarity due to normalized vectors
                
                if similarity >= self.similarity_threshold:
                    # Get metadata
                    metadata = self.cache_metadata.get(int(idx))
                    
                    if metadata:
                        # Check expiration
                        if self._is_expired(metadata['timestamp']):
                            logger.debug(f"Cache entry {idx} expired")
                            continue
                        
                        logger.info(f"Cache HIT! Similarity: {similarity:.4f} (threshold: {self.similarity_threshold})")
                        
                        return {
                            'response': metadata['response'],
                            'cached': True,
                            'cache_type': 'semantic',
                            'similarity_score': similarity,
                            'original_query': metadata['query'],
                            'cached_at': metadata['timestamp']
                        }
            
            logger.debug(f"Cache MISS. Best similarity: {distances[0][0]:.4f}")
            return None
        
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None
    
    def set(self, query: str, response: Dict[str, Any]) -> bool:
        """
        Cache query-response pair with embedding
        
        Args:
            query: User query text
            response: Response to cache
            
        Returns:
            True if cached successfully
        """
        if not self.embeddings:
            logger.warning("Embeddings not available, skipping cache storage")
            return False
        
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            query_vector = np.array([query_embedding], dtype=np.float32)
            query_vector = self._normalize_vector(query_vector)
            
            # Add to FAISS index
            self.index.add(query_vector)
            
            # Get new index ID
            index_id = self.index.ntotal - 1
            
            # Store metadata
            self.cache_metadata[index_id] = {
                'query': query,
                'response': response,
                'timestamp': datetime.now().isoformat(),
                'embedding': query_embedding  # Store for potential future use
            }
            
            # Store query hash mapping
            query_hash = self._generate_query_hash(query)
            self.query_to_index[query_hash] = index_id
            
            # Persist to disk
            self._save_cache()
            
            logger.info(f"Cached response for query: {query[:50]}...")
            return True
        
        except Exception as e:
            logger.error(f"Cache storage error: {e}")
            return False
    
    def invalidate_expired(self) -> int:
        """
        Remove expired cache entries
        
        Returns:
            Number of entries removed
        """
        try:
            expired_indices = []
            
            for idx, metadata in self.cache_metadata.items():
                if self._is_expired(metadata['timestamp']):
                    expired_indices.append(idx)
            
            if expired_indices:
                # Remove from metadata
                for idx in expired_indices:
                    del self.cache_metadata[idx]
                
                # Rebuild FAISS index (FAISS doesn't support deletion)
                if self.cache_metadata:
                    new_index = faiss.IndexFlatIP(self.dimension)
                    new_metadata = {}
                    
                    for new_idx, (old_idx, metadata) in enumerate(self.cache_metadata.items()):
                        # Add embedding to new index
                        embedding = np.array([metadata['embedding']], dtype=np.float32)
                        embedding = self._normalize_vector(embedding)
                        new_index.add(embedding)
                        
                        # Update metadata with new index
                        new_metadata[new_idx] = metadata
                    
                    self.index = new_index
                    self.cache_metadata = new_metadata
                    
                    # Rebuild query_to_index mapping
                    self.query_to_index = {}
                    for idx, metadata in self.cache_metadata.items():
                        query_hash = self._generate_query_hash(metadata['query'])
                        self.query_to_index[query_hash] = idx
                    
                    self._save_cache()
                
                logger.info(f"Invalidated {len(expired_indices)} expired cache entries")
                return len(expired_indices)
            
            return 0
        
        except Exception as e:
            logger.error(f"Error invalidating expired entries: {e}")
            return 0
    
    def clear(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            Number of entries cleared
        """
        try:
            count = self.index.ntotal
            
            # Reset index
            self.index = faiss.IndexFlatIP(self.dimension)
            self.cache_metadata = {}
            self.query_to_index = {}
            
            # Save empty cache
            self._save_cache()
            
            logger.info(f"Cleared {count} cache entries")
            return count
        
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            total_entries = self.index.ntotal
            
            # Count expired entries
            expired_count = sum(
                1 for metadata in self.cache_metadata.values()
                if self._is_expired(metadata['timestamp'])
            )
            
            # Calculate cache size
            cache_size_mb = 0
            if self.index_path.exists():
                cache_size_mb = self.index_path.stat().st_size / (1024 * 1024)
            
            return {
                'total_entries': total_entries,
                'active_entries': total_entries - expired_count,
                'expired_entries': expired_count,
                'cache_size_mb': round(cache_size_mb, 2),
                'similarity_threshold': self.similarity_threshold,
                'ttl_hours': self.ttl / 3600,
                'cache_directory': str(self.cache_dir)
            }
        
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
