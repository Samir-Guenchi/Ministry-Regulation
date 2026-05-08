"""
LLM-Powered Query Expansion Module
Uses LLM to dynamically generate synonyms and related terms instead of hardcoded dictionaries
"""
from typing import List, Dict, Set
from dataclasses import dataclass
import json
import logging
from groq import Groq
from graphrag.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMExpandedQuery:
    """LLM-generated expanded query"""
    original_query: str
    expanded_terms: List[str]
    synonyms: Dict[str, List[str]]
    related_terms: List[str]
    expanded_queries: List[str]
    context_terms: List[str]
    expansion_score: float


class LLMQueryExpander:
    """
    LLM-powered query expansion - No hardcoded dictionaries!
    
    Advantages over regex-based approach:
    - Learns from context dynamically
    - Handles new terms automatically
    - Understands semantic relationships
    - Works across any domain
    - No maintenance of dictionaries needed
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        
        # Minimal domain hints (optional)
        self.domain_context = "legal documents, ministry regulations, employment"
    
    def expand_query_with_llm(self, query: str, max_expansions: int = 10) -> LLMExpandedQuery:
        """
        Use LLM to expand query dynamically
        
        No hardcoded dictionaries - LLM generates everything!
        """
        
        # Build prompt for LLM
        prompt = f"""You are a query expansion expert for legal document search.

Given this query: "{query}"

Generate a JSON response with:
1. "key_terms": Extract 3-5 key terms from the query
2. "synonyms": For each key term, provide 3-5 synonyms (in same language)
3. "related_terms": 5-10 semantically related terms
4. "expanded_queries": 5-10 alternative phrasings of the query
5. "context_terms": Additional domain-specific terms that might help

Rules:
- Keep the same language as the input query
- For Arabic queries, provide Arabic expansions
- Focus on legal/employment terminology
- Be creative but relevant

Example for "شروط التوظيف":
{{
  "key_terms": ["شروط", "التوظيف"],
  "synonyms": {{
    "شروط": ["متطلبات", "مقتضيات", "ضوابط"],
    "التوظيف": ["التعيين", "التشغيل", "الاستخدام"]
  }},
  "related_terms": ["مسابقة", "اختبار", "ترشح", "وثائق", "شهادات"],
  "expanded_queries": [
    "متطلبات التعيين",
    "ما يلزم للتوظيف",
    "شروط الترشح للوظيفة"
  ],
  "context_terms": ["قانون", "مرسوم", "تنظيم"]
}}

Now expand this query: "{query}"

Respond ONLY with valid JSON."""

        try:
            # Call LLM
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a query expansion expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Creative but controlled
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            expansion_data = json.loads(response.choices[0].message.content)
            
            # Extract data
            key_terms = expansion_data.get("key_terms", [])
            synonyms = expansion_data.get("synonyms", {})
            related_terms = expansion_data.get("related_terms", [])
            expanded_queries = expansion_data.get("expanded_queries", [])
            context_terms = expansion_data.get("context_terms", [])
            
            # Calculate expansion score
            total_expansions = len(related_terms) + sum(len(syns) for syns in synonyms.values())
            expansion_score = min(1.0, total_expansions / 20)  # Normalize to 0-1
            
            # Collect all expanded terms
            all_expanded_terms = []
            for syns in synonyms.values():
                all_expanded_terms.extend(syns)
            all_expanded_terms.extend(related_terms)
            all_expanded_terms.extend(context_terms)
            
            result = LLMExpandedQuery(
                original_query=query,
                expanded_terms=list(set(all_expanded_terms)),
                synonyms=synonyms,
                related_terms=related_terms,
                expanded_queries=[query] + expanded_queries,  # Include original
                context_terms=context_terms,
                expansion_score=expansion_score
            )
            
            logger.info(
                f"LLM expanded query: {len(result.expanded_terms)} terms, "
                f"{len(result.expanded_queries)} variations"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"LLM expansion failed: {e}")
            # Fallback: return original query
            return LLMExpandedQuery(
                original_query=query,
                expanded_terms=[],
                synonyms={},
                related_terms=[],
                expanded_queries=[query],
                context_terms=[],
                expansion_score=0.0
            )
    
    def expand_for_retrieval(self, query: str) -> List[str]:
        """Expand query for retrieval - returns list of queries"""
        expansion = self.expand_query_with_llm(query)
        return expansion.expanded_queries[:10]  # Top 10
    
    def format_expansion_info(self, expansion: LLMExpandedQuery) -> str:
        """Format expansion information for display"""
        lines = []
        
        lines.append("🤖 **توسيع الاستعلام بالذكاء الاصطناعي**\n")
        lines.append(f"📝 **الاستعلام الأصلي**: {expansion.original_query}\n")
        
        if expansion.synonyms:
            lines.append("📚 **المرادفات المكتشفة:**")
            for term, syns in list(expansion.synonyms.items())[:5]:
                lines.append(f"  • {term}: {', '.join(syns[:3])}")
            lines.append("")
        
        if expansion.related_terms:
            lines.append("🔗 **المصطلحات ذات الصلة:**")
            lines.append(f"  {', '.join(expansion.related_terms[:8])}\n")
        
        if expansion.context_terms:
            lines.append("🎯 **مصطلحات السياق:**")
            lines.append(f"  {', '.join(expansion.context_terms[:5])}\n")
        
        if expansion.expanded_queries:
            lines.append(f"🎯 **استعلامات موسعة ({len(expansion.expanded_queries)}):**")
            for i, eq in enumerate(expansion.expanded_queries[:5], 1):
                lines.append(f"  {i}. {eq}")
            lines.append("")
        
        lines.append(f"📊 **درجة التوسيع**: {expansion.expansion_score:.0%}")
        lines.append("✨ **تم التوسيع باستخدام الذكاء الاصطناعي - لا قواميس مسبقة!**")
        
        return "\n".join(lines)
