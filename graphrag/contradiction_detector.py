"""
Contradiction Detection Module
Identifies and resolves conflicting information in retrieved documents
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Contradiction:
    """Represents a detected contradiction"""
    field: str  # What contradicts (e.g., "years_required", "salary")
    doc1_value: str
    doc2_value: str
    doc1_source: str
    doc2_source: str
    doc1_date: Optional[datetime]
    doc2_date: Optional[datetime]
    severity: str  # "high", "medium", "low"
    resolution: Optional[str]  # How to resolve


class ContradictionDetector:
    """
    Detects contradictions in retrieved documents
    - Extracts key facts from documents
    - Compares facts across documents
    - Resolves contradictions using temporal and hierarchical rules
    """
    
    def __init__(self):
        # Patterns for extracting numerical requirements
        self.number_patterns = {
            "years": [
                r"(\d+)\s+سنوات?\s+(?:من\s+)?(?:الخبرة|خبرة)",
                r"(\d+)\s+years?\s+(?:of\s+)?experience",
                r"(\d+)\s+ans?\s+d'expérience"
            ],
            "age": [
                r"(\d+)\s+سنة\s+(?:من\s+)?(?:العمر|عمر)",
                r"(\d+)\s+years?\s+old",
                r"(\d+)\s+ans"
            ],
            "salary": [
                r"(\d+(?:[.,]\d+)?)\s+(?:دينار|دج|DA)",
                r"(\d+(?:[.,]\d+)?)\s+(?:salary|salaire)"
            ],
            "positions": [
                r"(\d+)\s+(?:منصب|مناصب|poste|position)",
            ]
        }
        
        # Patterns for extracting requirements
        self.requirement_patterns = {
            "degree": [
                r"(?:شهادة|دبلوم)\s+(\w+(?:\s+\w+){0,3})",
                r"(?:degree|diploma)\s+(?:in\s+)?(\w+(?:\s+\w+){0,3})",
                r"(?:diplôme|licence)\s+(?:en\s+)?(\w+(?:\s+\w+){0,3})"
            ],
            "condition": [
                r"يشترط\s+(.+?)(?:\.|،|$)",
                r"(?:requires?|required)\s+(.+?)(?:\.|,|$)",
                r"(?:exige|requis)\s+(.+?)(?:\.|,|$)"
            ]
        }
    
    def extract_facts(self, document: Dict) -> Dict[str, List[str]]:
        """Extract key facts from document"""
        content = document.get("content", "")
        facts = {}
        
        # Extract numerical facts
        for fact_type, patterns in self.number_patterns.items():
            values = []
            for pattern in patterns:
                matches = re.findall(pattern, content)
                values.extend(matches)
            if values:
                facts[fact_type] = values
        
        # Extract requirement facts
        for fact_type, patterns in self.requirement_patterns.items():
            values = []
            for pattern in patterns:
                matches = re.findall(pattern, content)
                values.extend([m.strip() for m in matches if m.strip()])
            if values:
                facts[fact_type] = values
        
        return facts
    
    def compare_facts(
        self,
        doc1: Dict,
        doc2: Dict,
        facts1: Dict,
        facts2: Dict
    ) -> List[Contradiction]:
        """Compare facts between two documents"""
        contradictions = []
        
        # Compare common fact types
        common_types = set(facts1.keys()) & set(facts2.keys())
        
        for fact_type in common_types:
            values1 = set(facts1[fact_type])
            values2 = set(facts2[fact_type])
            
            # Check for contradictions
            if values1 != values2 and not (values1 & values2):
                # Get document metadata
                doc1_source = doc1.get("metadata", {}).get("source", "Unknown")
                doc2_source = doc2.get("metadata", {}).get("source", "Unknown")
                
                doc1_date = self._extract_date(doc1)
                doc2_date = self._extract_date(doc2)
                
                # Determine severity
                severity = self._determine_severity(fact_type, values1, values2)
                
                # Attempt resolution
                resolution = self._resolve_contradiction(
                    fact_type, values1, values2, doc1_date, doc2_date
                )
                
                contradiction = Contradiction(
                    field=fact_type,
                    doc1_value=", ".join(values1),
                    doc2_value=", ".join(values2),
                    doc1_source=doc1_source,
                    doc2_source=doc2_source,
                    doc1_date=doc1_date,
                    doc2_date=doc2_date,
                    severity=severity,
                    resolution=resolution
                )
                
                contradictions.append(contradiction)
                
                logger.warning(
                    f"Contradiction detected in {fact_type}: "
                    f"{contradiction.doc1_value} vs {contradiction.doc2_value}"
                )
        
        return contradictions
    
    def detect_contradictions(self, documents: List[Dict]) -> Tuple[List[Contradiction], Dict]:
        """Detect all contradictions in document set"""
        all_contradictions = []
        document_facts = []
        
        # Extract facts from all documents
        for doc in documents:
            facts = self.extract_facts(doc)
            document_facts.append((doc, facts))
        
        # Compare all pairs
        for i in range(len(document_facts)):
            for j in range(i + 1, len(document_facts)):
                doc1, facts1 = document_facts[i]
                doc2, facts2 = document_facts[j]
                
                contradictions = self.compare_facts(doc1, doc2, facts1, facts2)
                all_contradictions.extend(contradictions)
        
        # Build summary
        summary = {
            "total_contradictions": len(all_contradictions),
            "high_severity": len([c for c in all_contradictions if c.severity == "high"]),
            "medium_severity": len([c for c in all_contradictions if c.severity == "medium"]),
            "low_severity": len([c for c in all_contradictions if c.severity == "low"]),
            "resolved": len([c for c in all_contradictions if c.resolution]),
            "unresolved": len([c for c in all_contradictions if not c.resolution])
        }
        
        logger.info(f"Detected {len(all_contradictions)} contradictions: {summary}")
        
        return all_contradictions, summary
    
    def _extract_date(self, document: Dict) -> Optional[datetime]:
        """Extract date from document"""
        # Try metadata
        metadata = document.get("metadata", {})
        if "date" in metadata:
            try:
                return datetime.fromisoformat(metadata["date"])
            except:
                pass
        
        # Try document_date field
        if "document_date" in document:
            try:
                return datetime.fromisoformat(document["document_date"])
            except:
                pass
        
        # Try extracting from content
        content = document.get("content", "")
        date_pattern = r"(\d{4})"
        match = re.search(date_pattern, content)
        if match:
            try:
                year = int(match.group(1))
                if 1900 < year < 2100:
                    return datetime(year, 1, 1)
            except:
                pass
        
        return None
    
    def _determine_severity(
        self,
        fact_type: str,
        values1: set,
        values2: set
    ) -> str:
        """Determine contradiction severity"""
        
        # High severity for critical requirements
        if fact_type in ["years", "degree", "age"]:
            return "high"
        
        # Medium severity for numerical differences
        if fact_type in ["salary", "positions"]:
            return "medium"
        
        # Low severity for general conditions
        return "low"
    
    def _resolve_contradiction(
        self,
        fact_type: str,
        values1: set,
        values2: set,
        date1: Optional[datetime],
        date2: Optional[datetime]
    ) -> Optional[str]:
        """Attempt to resolve contradiction"""
        
        # Rule 1: Newer law supersedes older law
        if date1 and date2:
            if date1 > date2:
                return f"القانون الأحدث ({date1.year}) يسود: {', '.join(values1)}"
            elif date2 > date1:
                return f"القانون الأحدث ({date2.year}) يسود: {', '.join(values2)}"
        
        # Rule 2: More specific value (for numbers)
        if fact_type in ["years", "age", "salary"]:
            try:
                nums1 = [float(v.replace(",", ".")) for v in values1 if v.replace(",", ".").replace(".", "").isdigit()]
                nums2 = [float(v.replace(",", ".")) for v in values2 if v.replace(",", ".").replace(".", "").isdigit()]
                
                if nums1 and nums2:
                    # If one is a range and other is specific, prefer specific
                    if len(nums1) == 1 and len(nums2) > 1:
                        return f"القيمة المحددة: {nums1[0]}"
                    elif len(nums2) == 1 and len(nums1) > 1:
                        return f"القيمة المحددة: {nums2[0]}"
            except:
                pass
        
        # Rule 3: Cannot resolve - flag for user
        return None
    
    def build_contradiction_warning(
        self,
        contradictions: List[Contradiction],
        summary: Dict
    ) -> str:
        """Build warning message for contradictions"""
        
        if not contradictions:
            return ""
        
        warnings = []
        warnings.append("⚠️ **تنبيه: تم اكتشاف تعارض في المصادر**\n")
        
        # Show high severity contradictions
        high_severity = [c for c in contradictions if c.severity == "high"]
        
        for i, contradiction in enumerate(high_severity[:3], 1):  # Show max 3
            warnings.append(f"\n**تعارض {i}** ({contradiction.field}):")
            warnings.append(f"  • المصدر 1: {contradiction.doc1_value}")
            if contradiction.doc1_date:
                warnings.append(f"    (تاريخ: {contradiction.doc1_date.year})")
            warnings.append(f"  • المصدر 2: {contradiction.doc2_value}")
            if contradiction.doc2_date:
                warnings.append(f"    (تاريخ: {contradiction.doc2_date.year})")
            
            if contradiction.resolution:
                warnings.append(f"  ✅ **الحل**: {contradiction.resolution}")
            else:
                warnings.append(f"  ❌ **لم يتم الحل**: يُنصح بالتحقق من المصادر الرسمية")
        
        if len(high_severity) > 3:
            warnings.append(f"\n... و {len(high_severity) - 3} تعارضات أخرى")
        
        warnings.append(f"\n📊 **الإحصائيات**: {summary['resolved']} محلول، {summary['unresolved']} غير محلول")
        
        return "\n".join(warnings)
