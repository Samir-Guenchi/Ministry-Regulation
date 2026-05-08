"""
RAG Evaluation Metrics

Implements standard RAG evaluation metrics:
- Faithfulness: Answer is grounded in retrieved context
- Answer Relevancy: Answer addresses the question
- Context Relevancy: Retrieved context is relevant to question
- Context Precision: Relevant context ranked higher
- Context Recall: All relevant information retrieved
"""
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import logging
from groq import Groq
from graphrag.config import settings
import json

logger = logging.getLogger(__name__)


@dataclass
class RAGEvaluationResult:
    """RAG evaluation results"""
    faithfulness: float  # 0-1: Answer grounded in context
    answer_relevancy: float  # 0-1: Answer addresses question
    context_relevancy: float  # 0-1: Context relevant to question
    context_precision: float  # 0-1: Relevant context ranked higher
    context_recall: float  # 0-1: All relevant info retrieved
    overall_score: float  # Average of all metrics
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "faithfulness": round(self.faithfulness, 3),
            "answer_relevancy": round(self.answer_relevancy, 3),
            "context_relevancy": round(self.context_relevancy, 3),
            "context_precision": round(self.context_precision, 3),
            "context_recall": round(self.context_recall, 3),
            "overall_score": round(self.overall_score, 3)
        }


class RAGEvaluator:
    """Evaluate RAG system performance"""
    
    def __init__(self):
        self.groq_client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
    
    def evaluate(
        self,
        question: str,
        answer: str,
        retrieved_contexts: List[str],
        ground_truth: str = None
    ) -> RAGEvaluationResult:
        """
        Evaluate RAG response
        
        Args:
            question: User question
            answer: Generated answer
            retrieved_contexts: List of retrieved context chunks
            ground_truth: Optional ground truth answer for comparison
            
        Returns:
            RAGEvaluationResult with all metrics
        """
        # Calculate individual metrics
        faithfulness = self._calculate_faithfulness(answer, retrieved_contexts)
        answer_relevancy = self._calculate_answer_relevancy(question, answer)
        context_relevancy = self._calculate_context_relevancy(question, retrieved_contexts)
        context_precision = self._calculate_context_precision(question, retrieved_contexts)
        context_recall = self._calculate_context_recall(question, answer, retrieved_contexts)
        
        # Calculate overall score
        overall_score = (
            faithfulness + answer_relevancy + context_relevancy + 
            context_precision + context_recall
        ) / 5
        
        return RAGEvaluationResult(
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_relevancy=context_relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
            overall_score=overall_score
        )
    
    def _calculate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """
        Faithfulness: Measure if answer is grounded in retrieved context
        
        Uses LLM to check if statements in answer are supported by context
        """
        if not contexts:
            return 0.0
        
        try:
            # Extract claims from answer
            claims = self._extract_claims(answer)
            if not claims:
                return 1.0  # No claims to verify
            
            # Check each claim against context
            supported_claims = 0
            context_text = "\n\n".join(contexts)
            
            for claim in claims:
                if self._is_claim_supported(claim, context_text):
                    supported_claims += 1
            
            return supported_claims / len(claims)
        
        except Exception as e:
            logger.error(f"Error calculating faithfulness: {e}")
            return 0.5  # Default to neutral score
    
    def _calculate_answer_relevancy(self, question: str, answer: str) -> float:
        """
        Answer Relevancy: Measure if answer addresses the question
        
        Uses LLM to score relevancy
        """
        try:
            prompt = f"""Rate how well this answer addresses the question on a scale of 0-10.
Only respond with a number.

Question: {question}

Answer: {answer}

Rating (0-10):"""
            
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            rating_text = response.choices[0].message.content.strip()
            rating = float(re.search(r'\d+', rating_text).group())
            return min(rating / 10, 1.0)
        
        except Exception as e:
            logger.error(f"Error calculating answer relevancy: {e}")
            return 0.5
    
    def _calculate_context_relevancy(self, question: str, contexts: List[str]) -> float:
        """
        Context Relevancy: Measure if retrieved contexts are relevant to question
        """
        if not contexts:
            return 0.0
        
        try:
            relevant_count = 0
            
            for context in contexts:
                if self._is_context_relevant(question, context):
                    relevant_count += 1
            
            return relevant_count / len(contexts)
        
        except Exception as e:
            logger.error(f"Error calculating context relevancy: {e}")
            return 0.5
    
    def _calculate_context_precision(self, question: str, contexts: List[str]) -> float:
        """
        Context Precision: Measure if relevant contexts are ranked higher
        
        Checks if top-ranked contexts are more relevant
        """
        if not contexts:
            return 0.0
        
        try:
            # Check relevancy of top contexts
            top_n = min(3, len(contexts))
            top_contexts = contexts[:top_n]
            
            relevant_in_top = sum(
                1 for ctx in top_contexts 
                if self._is_context_relevant(question, ctx)
            )
            
            return relevant_in_top / top_n
        
        except Exception as e:
            logger.error(f"Error calculating context precision: {e}")
            return 0.5
    
    def _calculate_context_recall(
        self, 
        question: str, 
        answer: str, 
        contexts: List[str]
    ) -> float:
        """
        Context Recall: Measure if all relevant information was retrieved
        
        Checks if answer could be generated from retrieved contexts
        """
        if not contexts:
            return 0.0
        
        try:
            # Extract key information from answer
            key_info = self._extract_key_information(answer)
            if not key_info:
                return 1.0
            
            # Check if key info is in contexts
            context_text = "\n\n".join(contexts)
            found_info = sum(
                1 for info in key_info 
                if self._is_information_in_context(info, context_text)
            )
            
            return found_info / len(key_info)
        
        except Exception as e:
            logger.error(f"Error calculating context recall: {e}")
            return 0.5
    
    def _extract_claims(self, answer: str) -> List[str]:
        """Extract factual claims from answer"""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', answer)
        claims = [s.strip() for s in sentences if len(s.strip()) > 10]
        return claims[:5]  # Limit to 5 claims for efficiency
    
    def _is_claim_supported(self, claim: str, context: str) -> bool:
        """Check if claim is supported by context"""
        try:
            prompt = f"""Is this claim supported by the context? Answer only 'yes' or 'no'.

Claim: {claim}

Context: {context[:1000]}

Answer:"""
            
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            answer = response.choices[0].message.content.strip().lower()
            return 'yes' in answer or 'نعم' in answer
        
        except Exception as e:
            logger.error(f"Error checking claim support: {e}")
            return False
    
    def _is_context_relevant(self, question: str, context: str) -> bool:
        """Check if context is relevant to question"""
        try:
            prompt = f"""Is this context relevant to answering the question? Answer only 'yes' or 'no'.

Question: {question}

Context: {context[:500]}

Answer:"""
            
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            answer = response.choices[0].message.content.strip().lower()
            return 'yes' in answer or 'نعم' in answer
        
        except Exception as e:
            logger.error(f"Error checking context relevancy: {e}")
            return False
    
    def _extract_key_information(self, answer: str) -> List[str]:
        """Extract key information points from answer"""
        # Extract sentences with legal references
        sentences = re.split(r'[.!?]+', answer)
        key_info = []
        
        for sentence in sentences:
            # Look for legal references (laws, articles, etc.)
            if any(keyword in sentence for keyword in ['قانون', 'مادة', 'فصل', 'law', 'article']):
                key_info.append(sentence.strip())
        
        return key_info[:5]  # Limit to 5 key points
    
    def _is_information_in_context(self, info: str, context: str) -> bool:
        """Check if information is present in context"""
        # Simple keyword matching
        info_words = set(info.lower().split())
        context_words = set(context.lower().split())
        
        # Check overlap
        overlap = len(info_words & context_words)
        return overlap / len(info_words) > 0.5 if info_words else False
    
    def batch_evaluate(
        self,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate multiple test cases
        
        Args:
            test_cases: List of dicts with 'question', 'answer', 'contexts'
            
        Returns:
            Aggregated evaluation results
        """
        results = []
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"Evaluating test case {i+1}/{len(test_cases)}")
            
            result = self.evaluate(
                question=test_case['question'],
                answer=test_case['answer'],
                retrieved_contexts=test_case['contexts'],
                ground_truth=test_case.get('ground_truth')
            )
            
            results.append(result)
        
        # Calculate averages
        avg_metrics = {
            "faithfulness": sum(r.faithfulness for r in results) / len(results),
            "answer_relevancy": sum(r.answer_relevancy for r in results) / len(results),
            "context_relevancy": sum(r.context_relevancy for r in results) / len(results),
            "context_precision": sum(r.context_precision for r in results) / len(results),
            "context_recall": sum(r.context_recall for r in results) / len(results),
            "overall_score": sum(r.overall_score for r in results) / len(results)
        }
        
        return {
            "num_test_cases": len(test_cases),
            "average_metrics": avg_metrics,
            "individual_results": [r.to_dict() for r in results]
        }


# Global evaluator instance
evaluator = RAGEvaluator()
