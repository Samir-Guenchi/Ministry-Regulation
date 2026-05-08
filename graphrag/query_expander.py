"""
Query Expansion Module
Expands queries with synonyms, related terms, and legal terminology
"""
import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExpandedQuery:
    """Expanded query with variations"""
    original_query: str
    expanded_terms: List[str]
    synonyms: Dict[str, List[str]]
    related_terms: List[str]
    expanded_queries: List[str]
    expansion_score: float


class QueryExpander:
    """
    Expands queries to improve retrieval coverage
    - Adds synonyms and related terms
    - Handles legal terminology variations
    - Expands abbreviations
    - Adds morphological variations (Arabic)
    """
    
    def __init__(self):
        # Legal term synonyms (Arabic)
        self.synonyms = {
            # Employment terms
            "توظيف": ["تعيين", "تشغيل", "استخدام", "تكليف"],
            "وظيفة": ["منصب", "عمل", "خدمة", "مهمة"],
            "موظف": ["عامل", "مستخدم", "أجير", "مكلف"],
            
            # Requirements
            "شروط": ["متطلبات", "مقتضيات", "ضوابط", "معايير"],
            "يشترط": ["يتطلب", "يجب", "يلزم", "ينبغي"],
            "مطلوب": ["ضروري", "لازم", "واجب", "محتم"],
            
            # Qualifications
            "شهادة": ["دبلوم", "إجازة", "مؤهل", "وثيقة"],
            "خبرة": ["تجربة", "ممارسة", "دراية", "كفاءة"],
            "مؤهل": ["كفء", "قادر", "مستوف", "صالح"],
            
            # Positions
            "أستاذ": ["معلم", "مدرس", "محاضر", "مكون"],
            "طبيب": ["دكتور", "ممارس", "معالج"],
            "مهندس": ["تقني", "خبير"],
            
            # Documents
            "وثيقة": ["مستند", "ملف", "سجل", "شهادة"],
            "ملف": ["وثائق", "مستندات", "أوراق"],
            
            # Procedures
            "إجراء": ["عملية", "خطوة", "مسطرة", "طريقة"],
            "تقديم": ["إيداع", "تسليم", "عرض", "طرح"],
            "طلب": ["ترشح", "مطالبة", "استدعاء"],
            
            # Legal terms
            "قانون": ["تشريع", "نظام", "مرسوم", "قرار"],
            "مادة": ["فصل", "بند", "نص"],
            "حكم": ["نص", "قاعدة", "مقتضى"],
        }
        
        # English synonyms
        self.synonyms_en = {
            "requirement": ["condition", "prerequisite", "criterion", "qualification"],
            "position": ["post", "job", "role", "appointment"],
            "experience": ["expertise", "background", "practice"],
            "degree": ["diploma", "certificate", "qualification"],
            "apply": ["submit", "register", "enroll"],
        }
        
        # French synonyms
        self.synonyms_fr = {
            "exigence": ["condition", "critère", "prérequis"],
            "poste": ["emploi", "fonction", "position"],
            "expérience": ["pratique", "expertise"],
            "diplôme": ["certificat", "qualification"],
        }
        
        # Abbreviations
        self.abbreviations = {
            "أستاذ مساعد استشفائي جامعي": ["PAHU", "أ.م.ا.ج"],
            "أستاذ محاضر": ["أ.م", "MC"],
            "أستاذ التعليم العالي": ["أ.ت.ع", "PES"],
            "دكتوراه": ["PhD", "د."],
            "ماجستير": ["Master", "م."],
            "ليسانس": ["License", "ل."],
        }
        
        # Related terms (semantic expansion)
        self.related_terms = {
            "توظيف": ["مسابقة", "اختبار", "ترشح", "تعيين", "انتداب"],
            "شهادة": ["تكوين", "دراسة", "تخرج", "معادلة"],
            "خبرة": ["أقدمية", "ممارسة", "عمل", "تدريب"],
            "أستاذ": ["تدريس", "بحث", "جامعة", "تعليم"],
            "طبيب": ["صحة", "طب", "مستشفى", "علاج"],
        }
        
        # Morphological variations (Arabic root patterns)
        self.morphological_patterns = {
            "وظف": ["توظيف", "موظف", "وظيفة", "تو ظيف"],
            "علم": ["تعليم", "معلم", "علوم", "تعلم"],
            "درس": ["تدريس", "مدرس", "دراسة", "درس"],
        }
    
    def expand_query(self, query: str, max_expansions: int = 10) -> ExpandedQuery:
        """Expand query with synonyms and related terms"""
        
        # Detect language
        lang = self._detect_language(query)
        
        # Extract key terms
        key_terms = self._extract_key_terms(query)
        
        # Find synonyms
        query_synonyms = {}
        expanded_terms = []
        
        for term in key_terms:
            syns = self._find_synonyms(term, lang)
            if syns:
                query_synonyms[term] = syns
                expanded_terms.extend(syns)
        
        # Find related terms
        related = []
        for term in key_terms:
            related.extend(self._find_related_terms(term))
        
        # Expand abbreviations
        expanded_abbrev = self._expand_abbreviations(query)
        
        # Generate expanded queries
        expanded_queries = self._generate_expanded_queries(
            query, key_terms, query_synonyms, related, max_expansions
        )
        
        # Calculate expansion score
        expansion_score = len(expanded_terms) / max(len(key_terms), 1)
        
        result = ExpandedQuery(
            original_query=query,
            expanded_terms=list(set(expanded_terms)),
            synonyms=query_synonyms,
            related_terms=list(set(related)),
            expanded_queries=expanded_queries,
            expansion_score=min(1.0, expansion_score)
        )
        
        logger.info(
            f"Expanded query: {len(expanded_terms)} terms, "
            f"{len(expanded_queries)} variations, score: {expansion_score:.2f}"
        )
        
        return result
    
    def _detect_language(self, text: str) -> str:
        """Detect query language"""
        # Simple detection based on character sets
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        latin_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if arabic_chars > latin_chars:
            return "ar"
        elif "é" in text or "è" in text or "ê" in text:
            return "fr"
        else:
            return "en"
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from query"""
        # Remove stop words and extract meaningful terms
        stop_words = {
            "ما", "هي", "هل", "كيف", "متى", "أين", "من", "في", "على", "إلى",
            "what", "is", "are", "how", "when", "where", "who", "the", "a", "an",
            "quel", "est", "sont", "comment", "quand", "où", "qui", "le", "la", "les"
        }
        
        # Split into words
        words = re.findall(r'\w+', query)
        
        # Filter stop words and short words
        key_terms = [
            word for word in words
            if word.lower() not in stop_words and len(word) > 2
        ]
        
        return key_terms
    
    def _find_synonyms(self, term: str, lang: str) -> List[str]:
        """Find synonyms for a term"""
        term_lower = term.lower()
        
        # Check appropriate synonym dictionary
        if lang == "ar":
            return self.synonyms.get(term_lower, [])
        elif lang == "en":
            return self.synonyms_en.get(term_lower, [])
        elif lang == "fr":
            return self.synonyms_fr.get(term_lower, [])
        
        return []
    
    def _find_related_terms(self, term: str) -> List[str]:
        """Find semantically related terms"""
        term_lower = term.lower()
        return self.related_terms.get(term_lower, [])
    
    def _expand_abbreviations(self, query: str) -> List[str]:
        """Expand abbreviations in query"""
        expanded = []
        
        for full_form, abbrevs in self.abbreviations.items():
            # Check if query contains abbreviation
            for abbrev in abbrevs:
                if abbrev.lower() in query.lower():
                    expanded.append(full_form)
            
            # Check if query contains full form
            if full_form.lower() in query.lower():
                expanded.extend(abbrevs)
        
        return expanded
    
    def _generate_expanded_queries(
        self,
        original: str,
        key_terms: List[str],
        synonyms: Dict[str, List[str]],
        related: List[str],
        max_expansions: int
    ) -> List[str]:
        """Generate expanded query variations"""
        expanded_queries = [original]  # Always include original
        
        # Strategy 1: Replace each key term with its first synonym
        for term in key_terms:
            if term.lower() in synonyms and synonyms[term.lower()]:
                syn = synonyms[term.lower()][0]
                expanded = original.replace(term, syn)
                if expanded != original:
                    expanded_queries.append(expanded)
        
        # Strategy 2: Add related terms
        for rel_term in related[:3]:  # Top 3 related terms
            expanded = f"{original} {rel_term}"
            expanded_queries.append(expanded)
        
        # Strategy 3: Combine synonyms
        if len(key_terms) >= 2:
            for i, term1 in enumerate(key_terms[:2]):
                for term2 in key_terms[i+1:i+2]:
                    if term1.lower() in synonyms and term2.lower() in synonyms:
                        syn1 = synonyms[term1.lower()][0] if synonyms[term1.lower()] else term1
                        syn2 = synonyms[term2.lower()][0] if synonyms[term2.lower()] else term2
                        expanded = original.replace(term1, syn1).replace(term2, syn2)
                        if expanded != original:
                            expanded_queries.append(expanded)
        
        # Limit to max expansions
        return expanded_queries[:max_expansions]
    
    def expand_for_retrieval(self, query: str) -> List[str]:
        """Expand query specifically for retrieval (returns list of queries)"""
        expansion = self.expand_query(query)
        
        # Combine original + expanded queries
        all_queries = [expansion.original_query] + expansion.expanded_queries
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in all_queries:
            if q.lower() not in seen:
                seen.add(q.lower())
                unique_queries.append(q)
        
        return unique_queries
    
    def format_expansion_info(self, expansion: ExpandedQuery) -> str:
        """Format expansion information for display"""
        lines = []
        
        lines.append("🔍 **توسيع الاستعلام**\n")
        lines.append(f"📝 **الاستعلام الأصلي**: {expansion.original_query}\n")
        
        if expansion.synonyms:
            lines.append("📚 **المرادفات المكتشفة:**")
            for term, syns in list(expansion.synonyms.items())[:5]:
                lines.append(f"  • {term}: {', '.join(syns[:3])}")
            lines.append("")
        
        if expansion.related_terms:
            lines.append("🔗 **المصطلحات ذات الصلة:**")
            lines.append(f"  {', '.join(expansion.related_terms[:5])}\n")
        
        if expansion.expanded_queries:
            lines.append(f"🎯 **استعلامات موسعة ({len(expansion.expanded_queries)}):**")
            for i, eq in enumerate(expansion.expanded_queries[:5], 1):
                lines.append(f"  {i}. {eq}")
            lines.append("")
        
        lines.append(f"📊 **درجة التوسيع**: {expansion.expansion_score:.0%}")
        
        return "\n".join(lines)
