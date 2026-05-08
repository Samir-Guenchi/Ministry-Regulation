"""
Implicit Requirement Extractor
Discovers unstated requirements by analyzing patterns and dependencies
"""
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ImplicitRequirement:
    """Represents an implicit (unstated) requirement"""
    requirement: str
    confidence: float
    reasoning: str
    source_patterns: List[str]
    related_explicit_requirements: List[str]
    category: str  # "procedural", "qualification", "documentation", "temporal"


class ImplicitRequirementExtractor:
    """
    Extracts implicit requirements from legal documents
    - Analyzes co-occurrence patterns
    - Infers procedural requirements
    - Discovers documentation needs
    - Identifies temporal constraints
    """
    
    def __init__(self):
        # Common implicit requirement patterns
        self.implicit_patterns = {
            "documentation": [
                r"(?:شهادة|وثيقة|مستند)\s+(\w+(?:\s+\w+){0,3})",
                r"(?:certificate|document)\s+(?:of\s+)?(\w+(?:\s+\w+){0,3})",
                r"(?:certificat|document)\s+(?:de\s+)?(\w+(?:\s+\w+){0,3})"
            ],
            "procedural": [
                r"(?:يجب|ينبغي)\s+(.+?)\s+(?:قبل|بعد|عند)\s+(.+?)(?:\.|،|$)",
                r"(?:must|should)\s+(.+?)\s+(?:before|after|when)\s+(.+?)(?:\.|,|$)",
                r"(?:doit|devrait)\s+(.+?)\s+(?:avant|après|quand)\s+(.+?)(?:\.|,|$)"
            ],
            "qualification": [
                r"(?:معتمد|مصادق|موثق)\s+(?:من|لدى)\s+(\w+(?:\s+\w+){0,3})",
                r"(?:certified|accredited|approved)\s+by\s+(\w+(?:\s+\w+){0,3})",
                r"(?:certifié|accrédité|approuvé)\s+par\s+(\w+(?:\s+\w+){0,3})"
            ],
            "temporal": [
                r"(?:خلال|في غضون|قبل)\s+(\d+)\s+(?:يوم|شهر|سنة)",
                r"(?:within|before)\s+(\d+)\s+(?:days?|months?|years?)",
                r"(?:dans|avant)\s+(\d+)\s+(?:jours?|mois|ans?)"
            ]
        }
        
        # Requirement co-occurrence tracking
        self.requirement_cooccurrence = defaultdict(lambda: defaultdict(int))
    
    def extract_implicit_requirements(
        self,
        documents: List[Dict],
        explicit_requirements: List[str]
    ) -> List[ImplicitRequirement]:
        """Extract implicit requirements from documents"""
        implicit_reqs = []
        
        # 1. Pattern-based extraction
        pattern_reqs = self._extract_by_patterns(documents)
        implicit_reqs.extend(pattern_reqs)
        
        # 2. Co-occurrence analysis
        cooccurrence_reqs = self._extract_by_cooccurrence(documents, explicit_requirements)
        implicit_reqs.extend(cooccurrence_reqs)
        
        # 3. Procedural inference
        procedural_reqs = self._infer_procedural_requirements(documents)
        implicit_reqs.extend(procedural_reqs)
        
        # 4. Documentation inference
        doc_reqs = self._infer_documentation_requirements(documents, explicit_requirements)
        implicit_reqs.extend(doc_reqs)
        
        # Remove duplicates and sort by confidence
        implicit_reqs = self._deduplicate_requirements(implicit_reqs)
        implicit_reqs.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"Extracted {len(implicit_reqs)} implicit requirements")
        
        return implicit_reqs
    
    def _extract_by_patterns(self, documents: List[Dict]) -> List[ImplicitRequirement]:
        """Extract implicit requirements using patterns"""
        requirements = []
        
        for doc in documents:
            content = doc.get("content", "")
            law_name = doc.get("title", "Unknown")
            
            # Documentation requirements
            for pattern in self.implicit_patterns["documentation"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    doc_type = match.group(1).strip()
                    if len(doc_type) < 100:
                        req = ImplicitRequirement(
                            requirement=f"تقديم {doc_type}",
                            confidence=0.7,
                            reasoning=f"ذُكر في {law_name} كوثيقة مطلوبة",
                            source_patterns=[match.group(0)],
                            related_explicit_requirements=[],
                            category="documentation"
                        )
                        requirements.append(req)
            
            # Qualification requirements
            for pattern in self.implicit_patterns["qualification"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    authority = match.group(1).strip()
                    if len(authority) < 100:
                        req = ImplicitRequirement(
                            requirement=f"الاعتماد من {authority}",
                            confidence=0.75,
                            reasoning=f"يتطلب اعتماد من {authority} حسب {law_name}",
                            source_patterns=[match.group(0)],
                            related_explicit_requirements=[],
                            category="qualification"
                        )
                        requirements.append(req)
            
            # Temporal requirements
            for pattern in self.implicit_patterns["temporal"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    duration = match.group(1).strip()
                    req = ImplicitRequirement(
                        requirement=f"إنجاز الإجراء خلال {duration} وحدة زمنية",
                        confidence=0.8,
                        reasoning=f"مهلة زمنية محددة في {law_name}",
                        source_patterns=[match.group(0)],
                        related_explicit_requirements=[],
                        category="temporal"
                    )
                    requirements.append(req)
        
        return requirements
    
    def _extract_by_cooccurrence(
        self,
        documents: List[Dict],
        explicit_requirements: List[str]
    ) -> List[ImplicitRequirement]:
        """Extract requirements based on co-occurrence patterns"""
        requirements = []
        
        # Build co-occurrence matrix
        for doc in documents:
            content = doc.get("content", "").lower()
            
            # Find which explicit requirements appear in this document
            present_reqs = [req for req in explicit_requirements if req.lower() in content]
            
            # Track co-occurrences
            for i, req1 in enumerate(present_reqs):
                for req2 in present_reqs[i+1:]:
                    self.requirement_cooccurrence[req1][req2] += 1
                    self.requirement_cooccurrence[req2][req1] += 1
        
        # Find strong co-occurrences
        for req1, cooccur_dict in self.requirement_cooccurrence.items():
            for req2, count in cooccur_dict.items():
                if count >= 3:  # Appears together in at least 3 documents
                    confidence = min(0.9, 0.5 + (count * 0.1))
                    req = ImplicitRequirement(
                        requirement=f"إذا كان {req1} مطلوباً، فغالباً {req2} مطلوب أيضاً",
                        confidence=confidence,
                        reasoning=f"يظهران معاً في {count} وثائق",
                        source_patterns=[],
                        related_explicit_requirements=[req1, req2],
                        category="procedural"
                    )
                    requirements.append(req)
        
        return requirements
    
    def _infer_procedural_requirements(self, documents: List[Dict]) -> List[ImplicitRequirement]:
        """Infer procedural requirements from document structure"""
        requirements = []
        
        for doc in documents:
            content = doc.get("content", "")
            law_name = doc.get("title", "Unknown")
            
            # Look for procedural patterns
            for pattern in self.implicit_patterns["procedural"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    if len(match.groups()) >= 2:
                        action = match.group(1).strip()
                        condition = match.group(2).strip()
                        
                        if len(action) < 150 and len(condition) < 150:
                            req = ImplicitRequirement(
                                requirement=f"{action} {condition}",
                                confidence=0.75,
                                reasoning=f"إجراء مطلوب حسب {law_name}",
                                source_patterns=[match.group(0)],
                                related_explicit_requirements=[],
                                category="procedural"
                            )
                            requirements.append(req)
        
        return requirements
    
    def _infer_documentation_requirements(
        self,
        documents: List[Dict],
        explicit_requirements: List[str]
    ) -> List[ImplicitRequirement]:
        """Infer documentation requirements from explicit requirements"""
        requirements = []
        
        # Common documentation needs for different requirement types
        doc_inference_rules = {
            "خبرة": ["شهادة عمل", "كشف راتب", "عقد عمل"],
            "شهادة": ["نسخة مصادق عليها", "كشف نقاط", "معادلة الشهادة"],
            "experience": ["work certificate", "employment contract"],
            "degree": ["certified copy", "transcript", "diploma equivalence"],
            "expérience": ["certificat de travail", "contrat de travail"],
            "diplôme": ["copie certifiée", "relevé de notes"]
        }
        
        for explicit_req in explicit_requirements:
            req_lower = explicit_req.lower()
            
            for keyword, docs in doc_inference_rules.items():
                if keyword in req_lower:
                    for doc_type in docs:
                        req = ImplicitRequirement(
                            requirement=f"تقديم {doc_type}",
                            confidence=0.65,
                            reasoning=f"وثيقة ضرورية لإثبات {explicit_req}",
                            source_patterns=[],
                            related_explicit_requirements=[explicit_req],
                            category="documentation"
                        )
                        requirements.append(req)
        
        return requirements
    
    def _deduplicate_requirements(
        self,
        requirements: List[ImplicitRequirement]
    ) -> List[ImplicitRequirement]:
        """Remove duplicate requirements"""
        seen = set()
        unique = []
        
        for req in requirements:
            # Create a normalized key
            key = req.requirement.lower().strip()
            key = re.sub(r'\s+', ' ', key)
            
            if key not in seen:
                seen.add(key)
                unique.append(req)
        
        return unique
    
    def categorize_by_priority(
        self,
        requirements: List[ImplicitRequirement]
    ) -> Dict[str, List[ImplicitRequirement]]:
        """Categorize requirements by priority"""
        categorized = {
            "critical": [],  # High confidence, essential
            "important": [],  # Medium confidence, recommended
            "optional": []  # Low confidence, nice to have
        }
        
        for req in requirements:
            if req.confidence >= 0.8:
                categorized["critical"].append(req)
            elif req.confidence >= 0.6:
                categorized["important"].append(req)
            else:
                categorized["optional"].append(req)
        
        return categorized
    
    def format_implicit_requirements(
        self,
        requirements: List[ImplicitRequirement],
        max_display: int = 10
    ) -> str:
        """Format implicit requirements for display"""
        if not requirements:
            return ""
        
        lines = []
        lines.append("🔍 **متطلبات ضمنية مكتشفة:**\n")
        
        # Categorize
        categorized = self.categorize_by_priority(requirements)
        
        # Critical requirements
        if categorized["critical"]:
            lines.append("🔴 **متطلبات حرجة (ثقة عالية):**")
            for req in categorized["critical"][:5]:
                lines.append(f"  • {req.requirement}")
                lines.append(f"    السبب: {req.reasoning}")
                lines.append(f"    الثقة: {req.confidence:.0%}")
            lines.append("")
        
        # Important requirements
        if categorized["important"]:
            lines.append("🟠 **متطلبات مهمة (ثقة متوسطة):**")
            for req in categorized["important"][:3]:
                lines.append(f"  • {req.requirement}")
                lines.append(f"    السبب: {req.reasoning}")
            lines.append("")
        
        # Optional requirements
        if categorized["optional"] and len(categorized["critical"]) + len(categorized["important"]) < max_display:
            lines.append("🟡 **متطلبات اختيارية (للتحقق):**")
            for req in categorized["optional"][:2]:
                lines.append(f"  • {req.requirement}")
            lines.append("")
        
        lines.append("💡 **ملاحظة**: هذه متطلبات مستنتجة من تحليل الوثائق. يُنصح بالتحقق منها.")
        
        return "\n".join(lines)
