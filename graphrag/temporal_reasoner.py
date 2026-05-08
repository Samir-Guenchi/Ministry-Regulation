"""
Temporal Reasoning Module for Legal Documents
Handles time-based queries and law version control
"""
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TemporalContext:
    """Temporal context extracted from query"""
    query_date: Optional[datetime]
    is_current: bool
    is_historical: bool
    date_phrases: List[str]
    temporal_type: str  # "current", "historical", "range", "none"


@dataclass
class LawVersion:
    """Law version with temporal validity"""
    law_name: str
    version: str
    effective_date: datetime
    expiry_date: Optional[datetime]
    status: str  # "active", "repealed", "amended"
    superseded_by: Optional[str]


class TemporalReasoner:
    """
    Handles temporal reasoning for legal queries
    - Detects temporal context in queries
    - Filters documents by temporal validity
    - Resolves law versions based on date
    """
    
    def __init__(self):
        # Arabic temporal patterns
        self.temporal_patterns = {
            "current": [
                r"حالياً", r"الآن", r"في الوقت الحالي", r"اليوم",
                r"currently", r"now", r"today", r"actuellement"
            ],
            "year": [
                r"في\s+(\d{4})", r"سنة\s+(\d{4})", r"عام\s+(\d{4})",
                r"in\s+(\d{4})", r"year\s+(\d{4})", r"en\s+(\d{4})"
            ],
            "before": [
                r"قبل\s+(\d{4})", r"قبل\s+سنة\s+(\d{4})",
                r"before\s+(\d{4})", r"avant\s+(\d{4})"
            ],
            "after": [
                r"بعد\s+(\d{4})", r"بعد\s+سنة\s+(\d{4})",
                r"after\s+(\d{4})", r"après\s+(\d{4})"
            ],
            "between": [
                r"بين\s+(\d{4})\s+و\s+(\d{4})",
                r"between\s+(\d{4})\s+and\s+(\d{4})",
                r"entre\s+(\d{4})\s+et\s+(\d{4})"
            ]
        }
        
        # Date extraction patterns for documents
        self.date_patterns = [
            r"مؤرخ\s+في\s+(\d{1,2})\s+(\w+)\s+(\d{4})",  # مؤرخ في 04 جانفي 2018
            r"بتاريخ\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # بتاريخ 04/01/2018
            r"(\d{1,2})\s+(\w+)\s+(\d{4})",  # 04 جانفي 2018
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",  # 2018-01-04
        ]
        
        # Arabic month names
        self.arabic_months = {
            "جانفي": 1, "يناير": 1,
            "فيفري": 2, "فبراير": 2,
            "مارس": 3, "آذار": 3,
            "أفريل": 4, "أبريل": 4, "نيسان": 4,
            "ماي": 5, "مايو": 5, "أيار": 5,
            "جوان": 6, "يونيو": 6, "حزيران": 6,
            "جويلية": 7, "يوليو": 7, "تموز": 7,
            "أوت": 8, "أغسطس": 8, "آب": 8,
            "سبتمبر": 9, "أيلول": 9,
            "أكتوبر": 10, "تشرين الأول": 10,
            "نوفمبر": 11, "تشرين الثاني": 11,
            "ديسمبر": 12, "كانون الأول": 12
        }
    
    def extract_temporal_context(self, query: str) -> TemporalContext:
        """Extract temporal context from query"""
        query_lower = query.lower()
        
        # Check for current time references
        is_current = any(
            re.search(pattern, query_lower)
            for pattern in self.temporal_patterns["current"]
        )
        
        # Extract year mentions
        query_date = None
        date_phrases = []
        temporal_type = "none"
        
        # Check for specific year
        for pattern in self.temporal_patterns["year"]:
            match = re.search(pattern, query)
            if match:
                year = int(match.group(1))
                query_date = datetime(year, 1, 1)
                date_phrases.append(match.group(0))
                temporal_type = "historical"
                break
        
        # Check for "before" patterns
        if not query_date:
            for pattern in self.temporal_patterns["before"]:
                match = re.search(pattern, query)
                if match:
                    year = int(match.group(1))
                    query_date = datetime(year, 1, 1)
                    date_phrases.append(match.group(0))
                    temporal_type = "before"
                    break
        
        # Check for "after" patterns
        if not query_date:
            for pattern in self.temporal_patterns["after"]:
                match = re.search(pattern, query)
                if match:
                    year = int(match.group(1))
                    query_date = datetime(year, 1, 1)
                    date_phrases.append(match.group(0))
                    temporal_type = "after"
                    break
        
        # Check for range
        if not query_date:
            for pattern in self.temporal_patterns["between"]:
                match = re.search(pattern, query)
                if match:
                    year1 = int(match.group(1))
                    year2 = int(match.group(2))
                    query_date = datetime(year1, 1, 1)
                    date_phrases.append(match.group(0))
                    temporal_type = "range"
                    break
        
        # Default to current if no temporal context
        if is_current or temporal_type == "none":
            temporal_type = "current"
            is_current = True
        
        is_historical = temporal_type in ["historical", "before", "range"]
        
        logger.info(f"Temporal context: type={temporal_type}, date={query_date}, phrases={date_phrases}")
        
        return TemporalContext(
            query_date=query_date,
            is_current=is_current,
            is_historical=is_historical,
            date_phrases=date_phrases,
            temporal_type=temporal_type
        )
    
    def extract_document_date(self, text: str, metadata: Dict = None) -> Optional[datetime]:
        """Extract date from document text or metadata"""
        
        # Try metadata first
        if metadata:
            if "date" in metadata:
                try:
                    return datetime.fromisoformat(metadata["date"])
                except:
                    pass
            if "year" in metadata:
                try:
                    return datetime(int(metadata["year"]), 1, 1)
                except:
                    pass
        
        # Try extracting from text
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    
                    # Pattern: مؤرخ في 04 جانفي 2018
                    if len(groups) == 3 and groups[1] in self.arabic_months:
                        day = int(groups[0])
                        month = self.arabic_months[groups[1]]
                        year = int(groups[2])
                        return datetime(year, month, day)
                    
                    # Pattern: 2018-01-04
                    elif len(groups) == 3 and int(groups[0]) > 1900:
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                        return datetime(year, month, day)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse date: {e}")
                    continue
        
        return None
    
    def filter_documents_by_date(
        self,
        documents: List[Dict],
        temporal_context: TemporalContext
    ) -> List[Dict]:
        """Filter documents based on temporal context"""
        
        if temporal_context.temporal_type == "none":
            return documents
        
        filtered_docs = []
        
        for doc in documents:
            doc_date = self.extract_document_date(
                doc.get("content", ""),
                doc.get("metadata", {})
            )
            
            if not doc_date:
                # If no date found, include document with lower confidence
                doc["temporal_confidence"] = 0.5
                filtered_docs.append(doc)
                continue
            
            # Apply temporal filtering
            include = False
            confidence = 1.0
            
            if temporal_context.temporal_type == "current":
                # For current queries, prefer recent documents
                years_old = (datetime.now() - doc_date).days / 365
                if years_old < 5:
                    include = True
                    confidence = max(0.5, 1.0 - (years_old / 10))
            
            elif temporal_context.temporal_type == "historical":
                # For historical queries, match the year
                if temporal_context.query_date:
                    year_diff = abs(doc_date.year - temporal_context.query_date.year)
                    if year_diff <= 2:  # Within 2 years
                        include = True
                        confidence = max(0.5, 1.0 - (year_diff / 5))
            
            elif temporal_context.temporal_type == "before":
                if temporal_context.query_date and doc_date < temporal_context.query_date:
                    include = True
            
            elif temporal_context.temporal_type == "after":
                if temporal_context.query_date and doc_date > temporal_context.query_date:
                    include = True
            
            elif temporal_context.temporal_type == "range":
                # Already handled in historical
                include = True
            
            if include:
                doc["temporal_confidence"] = confidence
                doc["document_date"] = doc_date.isoformat()
                filtered_docs.append(doc)
        
        # Sort by temporal confidence
        filtered_docs.sort(key=lambda x: x.get("temporal_confidence", 0), reverse=True)
        
        logger.info(f"Filtered {len(documents)} → {len(filtered_docs)} documents by temporal context")
        
        return filtered_docs
    
    def build_temporal_explanation(
        self,
        temporal_context: TemporalContext,
        documents: List[Dict]
    ) -> str:
        """Build explanation of temporal filtering"""
        
        if temporal_context.temporal_type == "none":
            return ""
        
        explanations = []
        
        if temporal_context.temporal_type == "current":
            explanations.append("🕐 تم البحث عن القوانين الحالية والسارية المفعول")
        
        elif temporal_context.temporal_type == "historical":
            year = temporal_context.query_date.year if temporal_context.query_date else "N/A"
            explanations.append(f"📅 تم البحث عن القوانين السارية في سنة {year}")
        
        elif temporal_context.temporal_type == "before":
            year = temporal_context.query_date.year if temporal_context.query_date else "N/A"
            explanations.append(f"⏪ تم البحث عن القوانين الصادرة قبل سنة {year}")
        
        elif temporal_context.temporal_type == "after":
            year = temporal_context.query_date.year if temporal_context.query_date else "N/A"
            explanations.append(f"⏩ تم البحث عن القوانين الصادرة بعد سنة {year}")
        
        # Add document dates
        doc_dates = [
            doc.get("document_date", "").split("T")[0]
            for doc in documents[:3]
            if doc.get("document_date")
        ]
        
        if doc_dates:
            explanations.append(f"📋 المصادر المستخدمة من تواريخ: {', '.join(doc_dates)}")
        
        return "\n".join(explanations)
