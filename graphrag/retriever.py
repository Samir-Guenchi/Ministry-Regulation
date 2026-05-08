from typing import List, Dict, Any, Tuple
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from graphrag.graph_builder import GraphBuilder
from graphrag.config import settings
from graphrag.models import Citation
from graphrag.temporal_reasoner import TemporalReasoner, TemporalContext
from graphrag.contradiction_detector import ContradictionDetector
from graphrag.hierarchical_chunker import HierarchicalChunker
from graphrag.multi_hop_reasoner import MultiHopReasoner
from graphrag.query_expander import QueryExpander
from graphrag.cross_encoder_reranker import CrossEncoderReranker
import numpy as np
import logging
import os
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Graph-Hybrid Retrieval System
    
    Combines:
    1. Vector Search (FAISS with embeddings)
    2. Graph Traversal (Neo4j entity relationships)
    3. Reciprocal Rank Fusion (RRF) for result merging
    
    Optimized for legal document retrieval with entity awareness
    """
    
    def __init__(self):
        # Initialize embeddings
        if settings.openai_api_key:
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.openai_api_key
            )
        else:
            logger.warning("No OpenAI API key. Vector search will be limited.")
            self.embeddings = None
        
        self.graph_builder = GraphBuilder()
        self.vector_store = None
        self.k = 60  # RRF constant
        
        # Initialize Phase 1 modules (Temporal, Contradiction, Hierarchical)
        self.temporal_reasoner = TemporalReasoner()
        self.contradiction_detector = ContradictionDetector()
        self.hierarchical_chunker = HierarchicalChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        
        # Initialize Phase 3 modules (Multi-hop, Query Expansion, Cross-encoder)
        self.multi_hop_reasoner = MultiHopReasoner(retriever=self)
        self.query_expander = QueryExpander()
        self.cross_encoder_reranker = CrossEncoderReranker()
        
        # Load documents from data directory
        self.documents = self._load_documents_from_data_dir()
    
    def _load_documents_from_data_dir(self) -> List[Dict[str, Any]]:
        """
        Load documents from the data directory
        Supports JSON, TXT, and PDF files
        """
        documents = []
        data_dir = Path(settings.data_directory)
        
        if not data_dir.exists():
            logger.warning(f"Data directory not found: {data_dir}")
            return documents
        
        logger.info(f"Loading documents from: {data_dir}")
        
        # Load JSON files
        for json_file in data_dir.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'content' in item:
                            documents.append({
                                'content': item.get('content', ''),
                                'title': item.get('title', ''),
                                'source': str(json_file),
                                'metadata': item
                            })
                elif isinstance(data, dict) and 'content' in data:
                    documents.append({
                        'content': data.get('content', ''),
                        'title': data.get('title', ''),
                        'source': str(json_file),
                        'metadata': data
                    })
                
                logger.debug(f"Loaded {len(data) if isinstance(data, list) else 1} documents from {json_file.name}")
            
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")
        
        # Load TXT files
        for txt_file in data_dir.rglob("*.txt"):
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content.strip():
                    documents.append({
                        'content': content,
                        'title': txt_file.stem,
                        'source': str(txt_file),
                        'metadata': {'filename': txt_file.name}
                    })
                
                logger.debug(f"Loaded document from {txt_file.name}")
            
            except Exception as e:
                logger.error(f"Error loading {txt_file}: {e}")
        
        logger.info(f"Loaded {len(documents)} total documents from data directory")
        return documents
    
    def load_vector_store(self, persist_directory: str = "./vector_store"):
        """Load or create vector store"""
        if not self.embeddings:
            logger.warning("Cannot load vector store without embeddings")
            return
        
        try:
            self.vector_store = FAISS.load_local(
                persist_directory,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            logger.info("Vector store loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load vector store: {e}")
            self.vector_store = None
    
    def reciprocal_rank_fusion(
        self,
        vector_results: List[Tuple[Dict, float]],
        graph_results: List[Dict],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and graph results using Reciprocal Rank Fusion
        
        RRF formula: score(d) = Σ 1 / (k + rank(d))
        
        Args:
            vector_results: List of (document, score) from vector search
            graph_results: List of documents from graph traversal
            k: RRF constant (default 60)
            
        Returns:
            Fused and ranked results
        """
        # Create document ID mapping
        doc_scores = {}
        
        # Process vector results
        for rank, (doc, score) in enumerate(vector_results, start=1):
            doc_id = doc.get('content', '')[:100]  # Use content prefix as ID
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'doc': doc,
                    'score': 0.0,
                    'vector_rank': rank,
                    'graph_rank': None
                }
            doc_scores[doc_id]['score'] += 1 / (k + rank)
        
        # Process graph results
        for rank, doc in enumerate(graph_results, start=1):
            doc_id = doc.get('content', '')[:100]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'doc': doc,
                    'score': 0.0,
                    'vector_rank': None,
                    'graph_rank': rank
                }
            else:
                doc_scores[doc_id]['graph_rank'] = rank
            doc_scores[doc_id]['score'] += 1 / (k + rank)
        
        # Sort by RRF score
        ranked_docs = sorted(
            doc_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        
        return [item['doc'] for item in ranked_docs]
    
    def vector_search(self, query: str, k: int = 10) -> List[Tuple[Dict, float]]:
        """Perform vector similarity search"""
        if not self.vector_store:
            logger.warning("Vector store not initialized")
            return []
        
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            return [(doc.metadata, score) for doc, score in results]
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    def graph_search(self, query: str, entities: List[str], max_depth: int = 2) -> List[Dict]:
        """Perform graph traversal search"""
        try:
            # Extract entities from query
            query_entities = self.graph_builder.extract_entities_from_text(query, "", "")
            
            if not query_entities:
                return []
            
            # Get entity IDs
            entity_ids = [e.entity_id for e in query_entities]
            
            # Query graph
            graph_data = self.graph_builder.query_graph(entity_ids, max_depth)
            
            # Convert graph nodes to documents
            documents = []
            for node in graph_data.get('nodes', []):
                documents.append({
                    'content': node.get('name', ''),
                    'title': node.get('name', ''),
                    'entity_id': node.get('entity_id', ''),
                    'properties': node.get('properties', {}),
                    'source': 'graph'
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Graph search error: {e}")
            return []
    
    def hybrid_retrieve(
        self,
        query: str,
        max_results: int = 5,
        use_graph: bool = True
    ) -> Tuple[List[Dict], str]:
        """
        Perform hybrid retrieval combining vector and graph search
        
        Args:
            query: User query
            max_results: Maximum number of results
            use_graph: Whether to include graph search
            
        Returns:
            (results, retrieval_method)
        """
        # Vector search
        vector_results = self.vector_search(query, k=10)
        
        if not use_graph or not vector_results:
            # Vector-only retrieval
            results = [doc for doc, score in vector_results[:max_results]]
            return results, "vector"
        
        # Graph search
        entities = [doc.get('entity_id') for doc, score in vector_results if doc.get('entity_id')]
        graph_results = self.graph_search(query, entities, max_depth=2)
        
        if not graph_results:
            # Fallback to vector-only
            results = [doc for doc, score in vector_results[:max_results]]
            return results, "vector"
        
        # Apply RRF
        fused_results = self.reciprocal_rank_fusion(vector_results, graph_results, k=self.k)
        
        return fused_results[:max_results], "hybrid"
    
    def enhanced_retrieve(
        self,
        query: str,
        max_results: int = 5,
        use_graph: bool = True
    ) -> Tuple[List[Dict], str, Dict]:
        """
        Enhanced retrieval with temporal reasoning, contradiction detection, and hierarchical context
        
        Args:
            query: User query
            max_results: Maximum number of results
            use_graph: Whether to include graph search
            
        Returns:
            (results, retrieval_method, enhancements)
        """
        enhancements = {
            "temporal_context": None,
            "contradictions": [],
            "contradiction_summary": {},
            "temporal_explanation": "",
            "contradiction_warning": ""
        }
        
        # Step 1: Extract temporal context from query
        temporal_context = self.temporal_reasoner.extract_temporal_context(query)
        enhancements["temporal_context"] = temporal_context
        
        logger.info(f"Temporal context: {temporal_context.temporal_type}")
        
        # Step 2: Perform hybrid retrieval
        vector_results = self.vector_search(query, k=15)  # Get more for filtering
        
        if not use_graph or not vector_results:
            results = [doc for doc, score in vector_results]
        else:
            entities = [doc.get('entity_id') for doc, score in vector_results if doc.get('entity_id')]
            graph_results = self.graph_search(query, entities, max_depth=2)
            
            if graph_results:
                results = self.reciprocal_rank_fusion(vector_results, graph_results, k=self.k)
            else:
                results = [doc for doc, score in vector_results]
        
        # Step 3: Apply temporal filtering
        if temporal_context.temporal_type != "none":
            results = self.temporal_reasoner.filter_documents_by_date(results, temporal_context)
            enhancements["temporal_explanation"] = self.temporal_reasoner.build_temporal_explanation(
                temporal_context, results[:max_results]
            )
        
        # Step 4: Detect contradictions in top results
        top_results = results[:max_results * 2]  # Check more docs for contradictions
        contradictions, summary = self.contradiction_detector.detect_contradictions(top_results)
        
        enhancements["contradictions"] = contradictions
        enhancements["contradiction_summary"] = summary
        
        if contradictions:
            enhancements["contradiction_warning"] = self.contradiction_detector.build_contradiction_warning(
                contradictions, summary
            )
            logger.warning(f"Detected {len(contradictions)} contradictions in retrieved documents")
        
        # Step 5: Return top results with enhancements
        final_results = results[:max_results]
        
        # Add hierarchical context to results
        for doc in final_results:
            if "full_hierarchy" not in doc and "content" in doc:
                # Try to extract hierarchy from content
                chunks = self.hierarchical_chunker.chunk_document(doc)
                if chunks:
                    doc["full_hierarchy"] = chunks[0].full_hierarchy
                    doc["parent_context"] = chunks[0].parent_context
        
        method = "hybrid_enhanced" if use_graph else "vector_enhanced"
        
        return final_results, method, enhancements
    
    def enhanced_retrieve_v2(
        self,
        query: str,
        max_results: int = 5,
        use_graph: bool = True,
        use_multi_hop: bool = True,
        use_query_expansion: bool = True,
        use_reranking: bool = True
    ) -> Tuple[List[Dict], str, Dict]:
        """
        Advanced retrieval with all Phase 3 features:
        1. Query Expansion - Expands query with synonyms and related terms
        2. Multi-hop Reasoning - Handles complex questions requiring multiple steps
        3. Cross-encoder Re-ranking - Re-ranks results for better relevance
        
        Plus Phase 1 features:
        - Temporal reasoning
        - Contradiction detection
        - Hierarchical chunking
        
        Args:
            query: User query
            max_results: Maximum number of results
            use_graph: Whether to include graph search
            use_multi_hop: Whether to use multi-hop reasoning for complex questions
            use_query_expansion: Whether to expand query
            use_reranking: Whether to re-rank results
            
        Returns:
            (results, retrieval_method, enhancements)
        """
        enhancements = {
            "temporal_context": None,
            "contradictions": [],
            "contradiction_summary": {},
            "temporal_explanation": "",
            "contradiction_warning": "",
            "query_expansion": None,
            "multi_hop_reasoning": None,
            "reranking_summary": None,
            "is_complex_question": False
        }
        
        logger.info(f"Enhanced retrieval v2 - Query: {query[:50]}...")
        
        # Step 1: Check if question requires multi-hop reasoning
        is_complex = self.multi_hop_reasoner.is_complex_question(query) if use_multi_hop else False
        enhancements["is_complex_question"] = is_complex
        
        if is_complex and use_multi_hop:
            logger.info("Complex question detected - using multi-hop reasoning")
            
            # Perform multi-hop reasoning
            multi_hop_result = self.multi_hop_reasoner.perform_multi_hop_reasoning(query, max_hops=5)
            enhancements["multi_hop_reasoning"] = multi_hop_result
            
            # Extract documents from reasoning steps
            results = []
            for step in multi_hop_result.reasoning_steps:
                # Retrieve for each sub-query
                step_docs, _, _ = self.enhanced_retrieve(
                    step.query,
                    max_results=3,
                    use_graph=use_graph
                )
                results.extend(step_docs)
            
            # Remove duplicates
            seen_ids = set()
            unique_results = []
            for doc in results:
                doc_id = doc.get('content', '')[:100]
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_results.append(doc)
            
            results = unique_results[:max_results * 2]  # Get more for re-ranking
            method = "multi_hop"
        
        else:
            # Step 2: Query Expansion
            if use_query_expansion:
                expansion = self.query_expander.expand_query(query, max_expansions=5)
                enhancements["query_expansion"] = expansion
                
                logger.info(
                    f"Query expanded: {len(expansion.expanded_queries)} variations, "
                    f"score: {expansion.expansion_score:.2f}"
                )
                
                # Retrieve for each expanded query
                all_results = []
                for expanded_q in expansion.expanded_queries[:3]:  # Top 3 expansions
                    docs, _, _ = self.enhanced_retrieve(
                        expanded_q,
                        max_results=5,
                        use_graph=use_graph
                    )
                    all_results.extend(docs)
                
                # Remove duplicates
                seen_ids = set()
                unique_results = []
                for doc in all_results:
                    doc_id = doc.get('content', '')[:100]
                    if doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        unique_results.append(doc)
                
                results = unique_results[:max_results * 2]  # Get more for re-ranking
                method = "expanded_hybrid" if use_graph else "expanded_vector"
            
            else:
                # Standard enhanced retrieval
                results, method, phase1_enhancements = self.enhanced_retrieve(
                    query,
                    max_results=max_results * 2,  # Get more for re-ranking
                    use_graph=use_graph
                )
                
                # Merge Phase 1 enhancements
                enhancements.update(phase1_enhancements)
        
        # Step 3: Cross-encoder Re-ranking
        if use_reranking and results:
            logger.info(f"Re-ranking {len(results)} documents")
            
            reranked_results, rerank_summary = self.cross_encoder_reranker.rerank(
                query,
                results,
                top_k=max_results,
                return_scores=True
            )
            
            enhancements["reranking_summary"] = rerank_summary
            
            logger.info(
                f"Re-ranking complete: {rerank_summary.reranking_method}, "
                f"avg improvement: {rerank_summary.avg_score_improvement:.3f}"
            )
            
            final_results = reranked_results
            method = f"{method}_reranked"
        
        else:
            final_results = results[:max_results]
        
        # Step 4: Add hierarchical context to results
        for doc in final_results:
            if "full_hierarchy" not in doc and "content" in doc:
                chunks = self.hierarchical_chunker.chunk_document(doc)
                if chunks:
                    doc["full_hierarchy"] = chunks[0].full_hierarchy
                    doc["parent_context"] = chunks[0].parent_context
        
        # Step 5: Extract temporal context and detect contradictions (if not already done)
        if not enhancements.get("temporal_context"):
            temporal_context = self.temporal_reasoner.extract_temporal_context(query)
            enhancements["temporal_context"] = temporal_context
            
            if temporal_context.temporal_type != "none":
                final_results = self.temporal_reasoner.filter_documents_by_date(
                    final_results, temporal_context
                )
                enhancements["temporal_explanation"] = self.temporal_reasoner.build_temporal_explanation(
                    temporal_context, final_results
                )
        
        if not enhancements.get("contradictions"):
            contradictions, summary = self.contradiction_detector.detect_contradictions(final_results)
            enhancements["contradictions"] = contradictions
            enhancements["contradiction_summary"] = summary
            
            if contradictions:
                enhancements["contradiction_warning"] = self.contradiction_detector.build_contradiction_warning(
                    contradictions, summary
                )
        
        logger.info(
            f"Enhanced retrieval v2 complete: {len(final_results)} results, method: {method}, "
            f"complex: {is_complex}, expanded: {use_query_expansion}, reranked: {use_reranking}"
        )
        
        return final_results, method, enhancements
    
    def extract_citations(self, documents: List[Dict]) -> List[Citation]:
        """Extract citations from retrieved documents"""
        citations = []
        
        for doc in documents:
            citation = Citation(
                law_name=doc.get('title', 'Unknown'),
                article_number=doc.get('article_number'),
                year=doc.get('year', 'Unknown'),
                text_excerpt=doc.get('content', '')[:200],
                confidence=doc.get('score', 0.8),
                source_file=doc.get('file')
            )
            citations.append(citation)
        
        return citations
    
    def close(self):
        """Close connections"""
        self.graph_builder.close()
