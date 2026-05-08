"""
Cross-Encoder Re-ranking Module
Re-ranks retrieved documents using cross-encoder models for better relevance
"""
from typing import List, Dict, Tuple
from dataclasses import dataclass
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class RerankingResult:
    """Result of re-ranking operation"""
    original_rank: int
    new_rank: int
    document: Dict
    original_score: float
    rerank_score: float
    score_improvement: float


@dataclass
class RerankingSummary:
    """Summary of re-ranking operation"""
    total_documents: int
    reranked_documents: int
    avg_score_improvement: float
    top_k_changed: int
    reranking_method: str


class CrossEncoderReranker:
    """
    Re-ranks retrieved documents using cross-encoder scoring
    
    Cross-encoders jointly encode query and document for better relevance scoring
    More accurate than bi-encoders but slower (used for re-ranking top results)
    
    Features:
    - Query-document relevance scoring
    - Legal domain-specific scoring
    - Multi-lingual support (Arabic, English, French)
    - Fallback to heuristic scoring if model unavailable
    """
    
    def __init__(self, model_name: str = None, use_gpu: bool = False):
        """
        Initialize cross-encoder re-ranker
        
        Args:
            model_name: Pre-trained cross-encoder model (e.g., 'cross-encoder/ms-marco-MiniLM-L-6-v2')
            use_gpu: Whether to use GPU acceleration
        """
        self.model_name = model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"
        self.use_gpu = use_gpu
        self.model = None
        
        # Try to load model
        self._load_model()
        
        # Legal domain keywords for heuristic scoring
        self.legal_keywords = {
            "ar": [
                "قانون", "مرسوم", "قرار", "مادة", "فصل", "شروط", "متطلبات",
                "إجراءات", "وثائق", "شهادة", "توظيف", "تعيين", "مسابقة"
            ],
            "en": [
                "law", "decree", "regulation", "article", "section", "requirement",
                "procedure", "document", "certificate", "employment", "appointment"
            ],
            "fr": [
                "loi", "décret", "règlement", "article", "section", "exigence",
                "procédure", "document", "certificat", "emploi", "nomination"
            ]
        }
    
    def _load_model(self):
        """Load cross-encoder model"""
        try:
            from sentence_transformers import CrossEncoder
            
            self.model = CrossEncoder(
                self.model_name,
                max_length=512,
                device='cuda' if self.use_gpu else 'cpu'
            )
            
            logger.info(f"Loaded cross-encoder model: {self.model_name}")
        
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            self.model = None
        
        except Exception as e:
            logger.warning(f"Could not load cross-encoder model: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = None,
        return_scores: bool = True
    ) -> Tuple[List[Dict], RerankingSummary]:
        """
        Re-rank documents based on query relevance
        
        Args:
            query: User query
            documents: List of retrieved documents
            top_k: Return only top K documents (None = all)
            return_scores: Whether to add rerank scores to documents
            
        Returns:
            (reranked_documents, summary)
        """
        if not documents:
            return [], RerankingSummary(
                total_documents=0,
                reranked_documents=0,
                avg_score_improvement=0.0,
                top_k_changed=0,
                reranking_method="none"
            )
        
        # Store original ranks
        for i, doc in enumerate(documents):
            doc['_original_rank'] = i + 1
            doc['_original_score'] = doc.get('score', 0.0)
        
        # Score documents
        if self.model:
            reranked_docs, method = self._rerank_with_model(query, documents)
        else:
            reranked_docs, method = self._rerank_heuristic(query, documents)
        
        # Calculate improvements
        score_improvements = []
        top_k_changed = 0
        
        for i, doc in enumerate(reranked_docs):
            doc['_new_rank'] = i + 1
            
            # Calculate score improvement
            improvement = doc.get('_rerank_score', 0.0) - doc.get('_original_score', 0.0)
            score_improvements.append(improvement)
            
            # Check if top-k changed
            if top_k and i < top_k:
                if doc['_original_rank'] > top_k:
                    top_k_changed += 1
        
        # Build summary
        summary = RerankingSummary(
            total_documents=len(documents),
            reranked_documents=len(reranked_docs),
            avg_score_improvement=np.mean(score_improvements) if score_improvements else 0.0,
            top_k_changed=top_k_changed,
            reranking_method=method
        )
        
        # Return top-k if specified
        if top_k:
            reranked_docs = reranked_docs[:top_k]
        
        # Clean up temporary fields if not returning scores
        if not return_scores:
            for doc in reranked_docs:
                doc.pop('_original_rank', None)
                doc.pop('_original_score', None)
                doc.pop('_new_rank', None)
                doc.pop('_rerank_score', None)
        
        logger.info(
            f"Re-ranked {len(documents)} documents using {method}. "
            f"Avg improvement: {summary.avg_score_improvement:.3f}, "
            f"Top-{top_k} changed: {summary.top_k_changed}"
        )
        
        return reranked_docs, summary
    
    def _rerank_with_model(
        self,
        query: str,
        documents: List[Dict]
    ) -> Tuple[List[Dict], str]:
        """Re-rank using cross-encoder model"""
        
        # Prepare query-document pairs
        pairs = []
        for doc in documents:
            # Use title + content for scoring
            doc_text = f"{doc.get('title', '')} {doc.get('content', '')}"[:512]
            pairs.append([query, doc_text])
        
        # Score pairs
        try:
            scores = self.model.predict(pairs, show_progress_bar=False)
            
            # Add scores to documents
            for doc, score in zip(documents, scores):
                doc['_rerank_score'] = float(score)
            
            # Sort by rerank score
            reranked = sorted(documents, key=lambda x: x['_rerank_score'], reverse=True)
            
            return reranked, "cross_encoder_model"
        
        except Exception as e:
            logger.error(f"Model re-ranking failed: {e}")
            return self._rerank_heuristic(query, documents)
    
    def _rerank_heuristic(
        self,
        query: str,
        documents: List[Dict]
    ) -> Tuple[List[Dict], str]:
        """Re-rank using heuristic scoring (fallback)"""
        
        # Detect query language
        lang = self._detect_language(query)
        
        # Extract query terms
        query_terms = set(query.lower().split())
        
        # Score each document
        for doc in documents:
            score = 0.0
            
            doc_text = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
            doc_terms = set(doc_text.split())
            
            # 1. Term overlap score (0-1)
            if query_terms:
                overlap = len(query_terms & doc_terms) / len(query_terms)
                score += overlap * 0.4
            
            # 2. Legal keyword score (0-1)
            legal_kw = self.legal_keywords.get(lang, [])
            legal_count = sum(1 for kw in legal_kw if kw in doc_text)
            legal_score = min(1.0, legal_count / 5)  # Normalize to 0-1
            score += legal_score * 0.2
            
            # 3. Document length score (prefer medium-length docs)
            doc_len = len(doc.get('content', ''))
            if 100 <= doc_len <= 2000:
                length_score = 1.0
            elif doc_len < 100:
                length_score = doc_len / 100
            else:
                length_score = max(0.5, 2000 / doc_len)
            score += length_score * 0.1
            
            # 4. Title relevance (0-1)
            title = doc.get('title', '').lower()
            title_overlap = len(query_terms & set(title.split())) / max(len(query_terms), 1)
            score += title_overlap * 0.2
            
            # 5. Original score (0-1)
            original_score = doc.get('_original_score', 0.0)
            score += original_score * 0.1
            
            doc['_rerank_score'] = score
        
        # Sort by rerank score
        reranked = sorted(documents, key=lambda x: x['_rerank_score'], reverse=True)
        
        return reranked, "heuristic"
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection"""
        import re
        
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        latin_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if arabic_chars > latin_chars:
            return "ar"
        elif "é" in text or "è" in text:
            return "fr"
        else:
            return "en"
    
    def batch_rerank(
        self,
        queries: List[str],
        document_lists: List[List[Dict]],
        top_k: int = None
    ) -> List[Tuple[List[Dict], RerankingSummary]]:
        """
        Re-rank multiple query-document sets in batch
        
        Args:
            queries: List of queries
            document_lists: List of document lists (one per query)
            top_k: Return only top K documents per query
            
        Returns:
            List of (reranked_documents, summary) tuples
        """
        results = []
        
        for query, docs in zip(queries, document_lists):
            reranked, summary = self.rerank(query, docs, top_k=top_k)
            results.append((reranked, summary))
        
        return results
    
    def compare_rankings(
        self,
        original_docs: List[Dict],
        reranked_docs: List[Dict],
        top_k: int = 5
    ) -> Dict:
        """
        Compare original and reranked document orders
        
        Args:
            original_docs: Original document order
            reranked_docs: Reranked document order
            top_k: Focus on top K documents
            
        Returns:
            Comparison statistics
        """
        # Build ID mappings
        original_ids = [id(doc) for doc in original_docs[:top_k]]
        reranked_ids = [id(doc) for doc in reranked_docs[:top_k]]
        
        # Calculate metrics
        same_order = original_ids == reranked_ids
        
        # Count position changes
        position_changes = 0
        for i, doc_id in enumerate(reranked_ids):
            if doc_id in original_ids:
                original_pos = original_ids.index(doc_id)
                if original_pos != i:
                    position_changes += 1
        
        # New documents in top-k
        new_in_topk = len(set(reranked_ids) - set(original_ids))
        
        # Kendall's Tau (rank correlation)
        from scipy.stats import kendalltau
        
        # Map document IDs to ranks
        original_ranks = {doc_id: i for i, doc_id in enumerate(original_ids)}
        reranked_ranks = []
        
        for doc_id in reranked_ids:
            if doc_id in original_ranks:
                reranked_ranks.append(original_ranks[doc_id])
        
        if len(reranked_ranks) >= 2:
            tau, p_value = kendalltau(list(range(len(reranked_ranks))), reranked_ranks)
        else:
            tau, p_value = 1.0, 1.0
        
        return {
            "same_order": same_order,
            "position_changes": position_changes,
            "new_in_topk": new_in_topk,
            "kendall_tau": tau,
            "p_value": p_value,
            "top_k": top_k
        }
    
    def format_reranking_info(
        self,
        summary: RerankingSummary,
        top_results: List[Dict] = None,
        show_scores: bool = True
    ) -> str:
        """Format re-ranking information for display"""
        lines = []
        
        lines.append("🔄 **إعادة ترتيب النتائج**\n")
        lines.append(f"📊 **عدد الوثائق**: {summary.total_documents}")
        lines.append(f"🎯 **الطريقة**: {summary.reranking_method}")
        lines.append(f"📈 **تحسين متوسط الدرجات**: {summary.avg_score_improvement:.3f}")
        lines.append(f"🔀 **تغييرات في أفضل النتائج**: {summary.top_k_changed}\n")
        
        if top_results and show_scores:
            lines.append("🏆 **أفضل النتائج بعد إعادة الترتيب:**")
            for i, doc in enumerate(top_results[:5], 1):
                title = doc.get('title', 'Unknown')[:50]
                original_rank = doc.get('_original_rank', '?')
                rerank_score = doc.get('_rerank_score', 0.0)
                
                rank_change = ""
                if isinstance(original_rank, int) and original_rank != i:
                    change = original_rank - i
                    if change > 0:
                        rank_change = f" ⬆️ (+{change})"
                    else:
                        rank_change = f" ⬇️ ({change})"
                
                lines.append(f"  {i}. {title} (درجة: {rerank_score:.3f}){rank_change}")
        
        return "\n".join(lines)
