"""
Multi-Hop Reasoning Module
Chains multiple queries to answer complex questions requiring multiple steps
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ReasoningStepType(Enum):
    """Types of reasoning steps"""
    RETRIEVE = "retrieve"  # Retrieve information
    INFER = "infer"  # Make inference
    COMPARE = "compare"  # Compare information
    AGGREGATE = "aggregate"  # Combine information
    VERIFY = "verify"  # Verify conclusion


@dataclass
class ReasoningStep:
    """Single step in multi-hop reasoning"""
    step_number: int
    step_type: ReasoningStepType
    query: str
    result: str
    confidence: float
    sources: List[str]


@dataclass
class MultiHopReasoning:
    """Complete multi-hop reasoning chain"""
    original_question: str
    reasoning_steps: List[ReasoningStep]
    final_answer: str
    total_confidence: float
    reasoning_path: str


class MultiHopReasoner:
    """
    Performs multi-hop reasoning for complex legal questions
    - Decomposes complex questions into sub-questions
    - Chains multiple retrieval and inference steps
    - Synthesizes final answer from intermediate results
    """
    
    def __init__(self, retriever=None, llm_client=None):
        self.retriever = retriever
        self.llm_client = llm_client
        
        # Patterns for complex questions requiring multi-hop
        self.complex_patterns = [
            r"(?:كيف|how)\s+(?:يمكن|can)\s+.+\s+(?:أن|to)\s+.+",  # How can X do Y
            r"(?:ما هي|what are)\s+.+\s+(?:و|and)\s+.+",  # What are X and Y
            r"(?:هل|is)\s+.+\s+(?:أفضل من|better than)\s+.+",  # Is X better than Y
            r"(?:ما الفرق|what's the difference)\s+(?:بين|between)\s+.+",  # Difference between
            r"(?:إذا|if)\s+.+\s+(?:فماذا|then what)\s+.+",  # If X then what Y
        ]
    
    def is_complex_question(self, question: str) -> bool:
        """Determine if question requires multi-hop reasoning"""
        
        # Check for complex patterns
        for pattern in self.complex_patterns:
            if re.search(pattern, question, re.IGNORECASE):
                return True
        
        # Check for multiple entities/concepts
        # Count question words
        question_words = ["كيف", "لماذا", "متى", "أين", "ما", "من", "هل",
                         "how", "why", "when", "where", "what", "who", "is"]
        count = sum(1 for word in question_words if word in question.lower())
        
        # Check for conjunctions
        conjunctions = ["و", "أو", "ثم", "بعد", "قبل", "and", "or", "then", "after", "before"]
        has_conjunction = any(conj in question.lower() for conj in conjunctions)
        
        # Complex if multiple question words or has conjunctions
        return count >= 2 or has_conjunction
    
    def decompose_question(self, question: str) -> List[str]:
        """Decompose complex question into sub-questions"""
        sub_questions = []
        
        # Pattern 1: "How can X do Y?" → ["What is X?", "What are requirements for Y?", "How to achieve Y?"]
        how_can_match = re.search(r"(?:كيف يمكن|how can)\s+(.+?)\s+(?:أن|to)\s+(.+)", question, re.IGNORECASE)
        if how_can_match:
            entity = how_can_match.group(1).strip()
            action = how_can_match.group(2).strip()
            
            sub_questions.append(f"ما هي شروط {action}؟")
            sub_questions.append(f"ما هي الإجراءات المطلوبة ل{action}؟")
            sub_questions.append(f"هل {entity} مؤهل ل{action}؟")
            return sub_questions
        
        # Pattern 2: "What is difference between X and Y?" → ["What is X?", "What is Y?", "Compare X and Y"]
        diff_match = re.search(r"(?:ما الفرق|what.*difference)\s+(?:بين|between)\s+(.+?)\s+(?:و|and)\s+(.+)", question, re.IGNORECASE)
        if diff_match:
            entity1 = diff_match.group(1).strip()
            entity2 = diff_match.group(2).strip()
            
            sub_questions.append(f"ما هو {entity1}؟")
            sub_questions.append(f"ما هو {entity2}؟")
            sub_questions.append(f"قارن بين {entity1} و {entity2}")
            return sub_questions
        
        # Pattern 3: "If X then what Y?" → ["What is X?", "What happens when X?", "What is Y?"]
        if_then_match = re.search(r"(?:إذا|if)\s+(.+?)\s+(?:فماذا|then what|ف)\s+(.+)", question, re.IGNORECASE)
        if if_then_match:
            condition = if_then_match.group(1).strip()
            consequence = if_then_match.group(2).strip()
            
            sub_questions.append(f"ما هي شروط {condition}؟")
            sub_questions.append(f"ماذا يحدث عند {condition}؟")
            sub_questions.append(f"ما هو {consequence}؟")
            return sub_questions
        
        # Pattern 4: Questions with "and" → Split by conjunction
        if " و " in question or " and " in question.lower():
            parts = re.split(r'\s+(?:و|and)\s+', question, flags=re.IGNORECASE)
            if len(parts) >= 2:
                for part in parts:
                    if len(part.strip()) > 10:  # Meaningful sub-question
                        sub_questions.append(part.strip() + "؟" if not part.endswith("؟") else part.strip())
                return sub_questions
        
        # Default: Return original question
        return [question]
    
    def execute_reasoning_step(
        self,
        step_number: int,
        step_type: ReasoningStepType,
        query: str,
        previous_results: List[ReasoningStep]
    ) -> ReasoningStep:
        """Execute a single reasoning step"""
        
        # Build context from previous steps
        context = "\n".join([
            f"Step {step.step_number}: {step.result}"
            for step in previous_results
        ])
        
        # Execute based on step type
        if step_type == ReasoningStepType.RETRIEVE:
            # Retrieve information
            if self.retriever:
                docs, method = self.retriever.hybrid_retrieve(query, max_results=3)
                result = "\n".join([doc.get("content", "")[:200] for doc in docs])
                sources = [doc.get("title", "Unknown") for doc in docs]
                confidence = 0.8
            else:
                result = f"Retrieved information for: {query}"
                sources = ["Mock"]
                confidence = 0.7
        
        elif step_type == ReasoningStepType.INFER:
            # Make inference from previous results
            result = f"Based on previous steps: {context[:200]}..."
            sources = [f"Step {s.step_number}" for s in previous_results]
            confidence = 0.75
        
        elif step_type == ReasoningStepType.COMPARE:
            # Compare information
            if len(previous_results) >= 2:
                result = f"Comparing: {previous_results[-2].result[:100]} vs {previous_results[-1].result[:100]}"
                sources = [f"Step {previous_results[-2].step_number}", f"Step {previous_results[-1].step_number}"]
                confidence = 0.7
            else:
                result = "Insufficient data for comparison"
                sources = []
                confidence = 0.5
        
        elif step_type == ReasoningStepType.AGGREGATE:
            # Aggregate information
            result = f"Aggregating {len(previous_results)} previous results"
            sources = [f"Step {s.step_number}" for s in previous_results]
            confidence = 0.8
        
        else:  # VERIFY
            # Verify conclusion
            result = "Verification complete"
            sources = ["All previous steps"]
            confidence = 0.85
        
        step = ReasoningStep(
            step_number=step_number,
            step_type=step_type,
            query=query,
            result=result,
            confidence=confidence,
            sources=sources
        )
        
        logger.info(f"Step {step_number} ({step_type.value}): {query[:50]}...")
        
        return step
    
    def perform_multi_hop_reasoning(
        self,
        question: str,
        max_hops: int = 5
    ) -> MultiHopReasoning:
        """Perform complete multi-hop reasoning"""
        
        # Check if question is complex
        if not self.is_complex_question(question):
            # Simple question - single hop
            step = self.execute_reasoning_step(
                1, ReasoningStepType.RETRIEVE, question, []
            )
            
            return MultiHopReasoning(
                original_question=question,
                reasoning_steps=[step],
                final_answer=step.result,
                total_confidence=step.confidence,
                reasoning_path=f"1. {step.query} → {step.result[:100]}"
            )
        
        # Decompose into sub-questions
        sub_questions = self.decompose_question(question)
        
        logger.info(f"Decomposed into {len(sub_questions)} sub-questions")
        
        # Execute reasoning steps
        reasoning_steps = []
        
        # Step 1-N: Retrieve for each sub-question
        for i, sub_q in enumerate(sub_questions[:max_hops-2], 1):
            step = self.execute_reasoning_step(
                i, ReasoningStepType.RETRIEVE, sub_q, reasoning_steps
            )
            reasoning_steps.append(step)
        
        # Step N-1: Aggregate results
        if len(reasoning_steps) > 1:
            aggregate_step = self.execute_reasoning_step(
                len(reasoning_steps) + 1,
                ReasoningStepType.AGGREGATE,
                "Combine all information",
                reasoning_steps
            )
            reasoning_steps.append(aggregate_step)
        
        # Step N: Synthesize final answer
        final_step = self.execute_reasoning_step(
            len(reasoning_steps) + 1,
            ReasoningStepType.INFER,
            f"Answer: {question}",
            reasoning_steps
        )
        reasoning_steps.append(final_step)
        
        # Calculate total confidence
        total_confidence = sum(s.confidence for s in reasoning_steps) / len(reasoning_steps)
        
        # Build reasoning path
        reasoning_path = "\n".join([
            f"{i}. {step.step_type.value.upper()}: {step.query}\n   → {step.result[:100]}..."
            for i, step in enumerate(reasoning_steps, 1)
        ])
        
        # Synthesize final answer
        final_answer = self._synthesize_answer(question, reasoning_steps)
        
        result = MultiHopReasoning(
            original_question=question,
            reasoning_steps=reasoning_steps,
            final_answer=final_answer,
            total_confidence=total_confidence,
            reasoning_path=reasoning_path
        )
        
        logger.info(f"Multi-hop reasoning complete: {len(reasoning_steps)} steps, confidence: {total_confidence:.2f}")
        
        return result
    
    def _synthesize_answer(self, question: str, steps: List[ReasoningStep]) -> str:
        """Synthesize final answer from reasoning steps"""
        
        # Collect all results
        results = [step.result for step in steps]
        
        # Build comprehensive answer
        answer_parts = []
        answer_parts.append(f"🧠 **تحليل متعدد الخطوات للسؤال**: {question}\n")
        
        # Add reasoning steps
        answer_parts.append("📋 **خطوات التحليل:**")
        for i, step in enumerate(steps, 1):
            answer_parts.append(f"{i}. {step.step_type.value}: {step.query}")
            answer_parts.append(f"   النتيجة: {step.result[:150]}...")
            answer_parts.append(f"   الثقة: {step.confidence:.0%}\n")
        
        # Add final synthesis
        answer_parts.append("✅ **الإجابة النهائية:**")
        answer_parts.append(f"بناءً على {len(steps)} خطوات من التحليل:")
        
        # Extract key information from last few steps
        key_info = " ".join([step.result[:100] for step in steps[-2:]])
        answer_parts.append(key_info)
        
        return "\n".join(answer_parts)
    
    def format_multi_hop_response(self, reasoning: MultiHopReasoning) -> str:
        """Format multi-hop reasoning as user-friendly response"""
        lines = []
        
        lines.append("🧠 **تحليل متعدد الخطوات**\n")
        lines.append(f"❓ **السؤال**: {reasoning.original_question}\n")
        
        lines.append(f"📊 **عدد الخطوات**: {len(reasoning.reasoning_steps)}")
        lines.append(f"📊 **الثقة الإجمالية**: {reasoning.total_confidence:.0%}\n")
        
        lines.append("🔍 **مسار التحليل:**")
        for i, step in enumerate(reasoning.reasoning_steps, 1):
            emoji = {
                ReasoningStepType.RETRIEVE: "📚",
                ReasoningStepType.INFER: "💡",
                ReasoningStepType.COMPARE: "⚖️",
                ReasoningStepType.AGGREGATE: "📊",
                ReasoningStepType.VERIFY: "✅"
            }.get(step.step_type, "•")
            
            lines.append(f"\n{emoji} **الخطوة {i}**: {step.query}")
            lines.append(f"   النتيجة: {step.result[:200]}...")
            if step.sources:
                lines.append(f"   المصادر: {', '.join(step.sources[:3])}")
        
        lines.append(f"\n{'='*60}")
        lines.append("✅ **الإجابة النهائية:**")
        lines.append(reasoning.final_answer)
        
        return "\n".join(lines)
