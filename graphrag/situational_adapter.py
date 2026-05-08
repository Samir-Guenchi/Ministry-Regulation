"""
Situational Adapter
Personalizes legal advice based on user's specific context and situation
"""
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class UserCategory(Enum):
    """User categories for specialized handling"""
    MEDICAL_PROFESSIONAL = "medical_professional"
    ACADEMIC = "academic"
    ENGINEER = "engineer"
    CIVIL_SERVANT = "civil_servant"
    PRIVATE_SECTOR = "private_sector"
    STUDENT = "student"
    FOREIGN_NATIONAL = "foreign_national"
    GENERAL = "general"


@dataclass
class UserProfile:
    """User profile extracted from query and context"""
    category: UserCategory
    profession: Optional[str] = None
    experience_years: Optional[int] = None
    education_level: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    current_position: Optional[str] = None
    special_circumstances: List[str] = None
    
    def __post_init__(self):
        if self.special_circumstances is None:
            self.special_circumstances = []


@dataclass
class PersonalizedAdvice:
    """Personalized legal advice"""
    general_answer: str
    personalized_insights: List[str]
    applicable_exceptions: List[str]
    specific_recommendations: List[str]
    relevant_laws: List[Dict]
    confidence: float


class SituationalAdapter:
    """
    Adapts legal responses based on user's specific situation
    - Identifies user category and profile
    - Finds applicable exceptions and special cases
    - Provides personalized recommendations
    - Highlights relevant laws for user's situation
    """
    
    def __init__(self):
        # Category detection patterns
        self.category_patterns = {
            UserCategory.MEDICAL_PROFESSIONAL: [
                r"(?:طبيب|دكتور|صيدلي|ممرض|جراح)",
                r"(?:doctor|physician|surgeon|nurse|pharmacist)",
                r"(?:médecin|docteur|chirurgien|infirmier|pharmacien)"
            ],
            UserCategory.ACADEMIC: [
                r"(?:أستاذ|باحث|معلم|محاضر)",
                r"(?:professor|teacher|researcher|lecturer)",
                r"(?:professeur|enseignant|chercheur)"
            ],
            UserCategory.ENGINEER: [
                r"(?:مهندس|تقني)",
                r"(?:engineer|technician)",
                r"(?:ingénieur|technicien)"
            ],
            UserCategory.STUDENT: [
                r"(?:طالب|دارس)",
                r"(?:student)",
                r"(?:étudiant)"
            ],
            UserCategory.FOREIGN_NATIONAL: [
                r"(?:أجنبي|غير جزائري|من الخارج)",
                r"(?:foreign|non-algerian|international)",
                r"(?:étranger|non-algérien)"
            ]
        }
        
        # Special law patterns for different categories
        self.special_law_patterns = {
            UserCategory.MEDICAL_PROFESSIONAL: [
                r"(?:قانون|مرسوم).*(?:صحة|طب|استشفائي)",
                r"(?:law|decree).*(?:health|medical|hospital)",
                r"(?:loi|décret).*(?:santé|médical|hospitalier)"
            ],
            UserCategory.ACADEMIC: [
                r"(?:قانون|مرسوم).*(?:تعليم|جامع|بحث)",
                r"(?:law|decree).*(?:education|university|research)",
                r"(?:loi|décret).*(?:éducation|universitaire|recherche)"
            ]
        }
        
        # Exception keywords
        self.exception_keywords = [
            "استثناء", "خاص", "حالة خاصة", "فئة خاصة",
            "exception", "special case", "specific category",
            "exception", "cas spécial", "catégorie spécifique"
        ]
    
    def extract_user_profile(self, query: str, context: Dict = None) -> UserProfile:
        """Extract user profile from query and context"""
        
        # Detect category
        category = self._detect_category(query)
        
        # Extract profession
        profession = self._extract_profession(query)
        
        # Extract experience years
        experience_years = self._extract_experience_years(query)
        
        # Extract education level
        education_level = self._extract_education_level(query)
        
        # Extract age
        age = self._extract_age(query)
        
        # Extract nationality
        nationality = self._extract_nationality(query)
        
        # Extract current position
        current_position = self._extract_current_position(query)
        
        # Detect special circumstances
        special_circumstances = self._detect_special_circumstances(query)
        
        profile = UserProfile(
            category=category,
            profession=profession,
            experience_years=experience_years,
            education_level=education_level,
            age=age,
            nationality=nationality,
            current_position=current_position,
            special_circumstances=special_circumstances
        )
        
        logger.info(f"Extracted user profile: category={category.value}, profession={profession}")
        
        return profile
    
    def find_applicable_exceptions(
        self,
        profile: UserProfile,
        documents: List[Dict]
    ) -> List[Dict]:
        """Find exceptions and special cases applicable to user"""
        exceptions = []
        
        for doc in documents:
            content = doc.get("content", "")
            law_name = doc.get("title", "Unknown")
            
            # Check for exception keywords
            has_exception = any(keyword in content.lower() for keyword in self.exception_keywords)
            
            if not has_exception:
                continue
            
            # Check if it's relevant to user's category
            is_relevant = False
            
            if profile.category in self.special_law_patterns:
                patterns = self.special_law_patterns[profile.category]
                is_relevant = any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)
            
            # Check for profession-specific mentions
            if profile.profession and profile.profession.lower() in content.lower():
                is_relevant = True
            
            if is_relevant:
                exceptions.append({
                    "law": law_name,
                    "content": content[:500],  # First 500 chars
                    "article": doc.get("article_number"),
                    "relevance": "high" if profile.profession and profile.profession.lower() in content.lower() else "medium"
                })
        
        logger.info(f"Found {len(exceptions)} applicable exceptions for {profile.category.value}")
        
        return exceptions
    
    def generate_personalized_advice(
        self,
        profile: UserProfile,
        general_answer: str,
        documents: List[Dict],
        exceptions: List[Dict]
    ) -> PersonalizedAdvice:
        """Generate personalized advice based on user profile"""
        
        personalized_insights = []
        applicable_exceptions = []
        specific_recommendations = []
        relevant_laws = []
        
        # Category-specific insights
        if profile.category == UserCategory.MEDICAL_PROFESSIONAL:
            personalized_insights.append(
                "🏥 كمهني صحي، قد تخضع لقوانين خاصة بالقطاع الصحي"
            )
            if profile.experience_years and profile.experience_years < 5:
                personalized_insights.append(
                    "💡 للأطباء الجدد: قد تكون هناك برامج تكوين خاصة تقلل من متطلبات الخبرة"
                )
        
        elif profile.category == UserCategory.ACADEMIC:
            personalized_insights.append(
                "🎓 كأكاديمي، قد تستفيد من قوانين خاصة بالتعليم العالي"
            )
            if profile.education_level and "دكتوراه" in profile.education_level.lower():
                personalized_insights.append(
                    "📚 حاملو الدكتوراه قد يستفيدون من مسارات مختصرة"
                )
        
        elif profile.category == UserCategory.FOREIGN_NATIONAL:
            personalized_insights.append(
                "🌍 كأجنبي، ستحتاج إلى وثائق إضافية ومعادلة للشهادات"
            )
            specific_recommendations.append(
                "تواصل مع وزارة الخارجية لمعادلة الشهادات"
            )
        
        # Experience-based insights
        if profile.experience_years:
            if profile.experience_years < 3:
                personalized_insights.append(
                    f"⏱️ مع {profile.experience_years} سنوات خبرة، قد تحتاج لمزيد من الوقت أو برامج تدريب"
                )
            elif profile.experience_years >= 10:
                personalized_insights.append(
                    f"⭐ مع {profile.experience_years} سنوات خبرة، قد تكون مؤهلاً لمناصب عليا"
                )
        
        # Exception-based advice
        for exception in exceptions:
            applicable_exceptions.append(
                f"📋 {exception['law']}: يحتوي على أحكام خاصة قد تنطبق عليك"
            )
            if exception.get("article"):
                applicable_exceptions.append(f"   المادة {exception['article']}")
        
        # General recommendations based on profile
        if profile.category != UserCategory.GENERAL:
            specific_recommendations.append(
                f"ابحث عن القوانين الخاصة بفئة {self._get_category_name_ar(profile.category)}"
            )
        
        if profile.special_circumstances:
            specific_recommendations.append(
                "تحقق من الاستثناءات المتعلقة بظروفك الخاصة"
            )
        
        # Find most relevant laws
        relevant_laws = self._find_relevant_laws(profile, documents)
        
        # Calculate confidence
        confidence = self._calculate_personalization_confidence(
            profile, exceptions, relevant_laws
        )
        
        advice = PersonalizedAdvice(
            general_answer=general_answer,
            personalized_insights=personalized_insights,
            applicable_exceptions=applicable_exceptions,
            specific_recommendations=specific_recommendations,
            relevant_laws=relevant_laws,
            confidence=confidence
        )
        
        return advice
    
    def _detect_category(self, query: str) -> UserCategory:
        """Detect user category from query"""
        query_lower = query.lower()
        
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return category
        
        return UserCategory.GENERAL
    
    def _extract_profession(self, query: str) -> Optional[str]:
        """Extract profession from query"""
        profession_patterns = [
            r"(?:أنا|أعمل)\s+(\w+(?:\s+\w+){0,2})",
            r"(?:I am|I work as)\s+(?:a\s+)?(\w+(?:\s+\w+){0,2})",
            r"(?:je suis|je travaille comme)\s+(\w+(?:\s+\w+){0,2})"
        ]
        
        for pattern in profession_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_experience_years(self, query: str) -> Optional[int]:
        """Extract years of experience"""
        patterns = [
            r"(?:لدي|عندي)\s+(\d+)\s+(?:سنوات?|سنة)\s+(?:من\s+)?(?:الخبرة|خبرة)",
            r"(?:I have|with)\s+(\d+)\s+years?\s+(?:of\s+)?experience",
            r"(?:j'ai|avec)\s+(\d+)\s+ans?\s+d'expérience"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_education_level(self, query: str) -> Optional[str]:
        """Extract education level"""
        patterns = [
            r"(?:لدي|حاصل على)\s+(?:شهادة|دبلوم)\s+(\w+(?:\s+\w+){0,2})",
            r"(?:I have|with)\s+(?:a\s+)?(\w+)\s+degree",
            r"(?:j'ai|avec)\s+(?:un\s+)?(?:diplôme|licence)\s+(?:de\s+)?(\w+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_age(self, query: str) -> Optional[int]:
        """Extract age"""
        patterns = [
            r"(?:عمري|سني)\s+(\d+)",
            r"(?:I am|I'm)\s+(\d+)\s+years?\s+old",
            r"(?:j'ai)\s+(\d+)\s+ans"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    def _extract_nationality(self, query: str) -> Optional[str]:
        """Extract nationality"""
        patterns = [
            r"(?:أنا|جنسيتي)\s+(\w+)",
            r"(?:I am|nationality)\s+(\w+)",
            r"(?:je suis|nationalité)\s+(\w+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                nationality = match.group(1).strip()
                if nationality.lower() not in ["أنا", "i", "je"]:
                    return nationality
        
        return None
    
    def _extract_current_position(self, query: str) -> Optional[str]:
        """Extract current position"""
        patterns = [
            r"(?:أعمل|منصبي)\s+(\w+(?:\s+\w+){0,3})",
            r"(?:I work as|my position is)\s+(\w+(?:\s+\w+){0,3})",
            r"(?:je travaille comme|mon poste est)\s+(\w+(?:\s+\w+){0,3})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _detect_special_circumstances(self, query: str) -> List[str]:
        """Detect special circumstances"""
        circumstances = []
        
        special_keywords = {
            "إعاقة": "disability",
            "حامل": "pregnant",
            "متزوج": "married",
            "أرمل": "widowed",
            "مطلق": "divorced"
        }
        
        query_lower = query.lower()
        for keyword, circumstance in special_keywords.items():
            if keyword in query_lower:
                circumstances.append(circumstance)
        
        return circumstances
    
    def _find_relevant_laws(self, profile: UserProfile, documents: List[Dict]) -> List[Dict]:
        """Find most relevant laws for user profile"""
        relevant = []
        
        for doc in documents:
            content = doc.get("content", "").lower()
            relevance_score = 0
            
            # Check category relevance
            if profile.category in self.special_law_patterns:
                patterns = self.special_law_patterns[profile.category]
                if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                    relevance_score += 3
            
            # Check profession mention
            if profile.profession and profile.profession.lower() in content:
                relevance_score += 2
            
            # Check education level
            if profile.education_level and profile.education_level.lower() in content:
                relevance_score += 1
            
            if relevance_score > 0:
                relevant.append({
                    "law": doc.get("title", "Unknown"),
                    "relevance_score": relevance_score,
                    "article": doc.get("article_number")
                })
        
        # Sort by relevance
        relevant.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return relevant[:5]
    
    def _calculate_personalization_confidence(
        self,
        profile: UserProfile,
        exceptions: List[Dict],
        relevant_laws: List[Dict]
    ) -> float:
        """Calculate confidence in personalization"""
        confidence = 0.5  # Base confidence
        
        # Increase based on profile completeness
        if profile.profession:
            confidence += 0.1
        if profile.experience_years is not None:
            confidence += 0.1
        if profile.education_level:
            confidence += 0.1
        
        # Increase based on found exceptions
        if exceptions:
            confidence += min(0.2, len(exceptions) * 0.05)
        
        # Increase based on relevant laws
        if relevant_laws:
            confidence += min(0.1, len(relevant_laws) * 0.02)
        
        return min(1.0, confidence)
    
    def _get_category_name_ar(self, category: UserCategory) -> str:
        """Get Arabic name for category"""
        names = {
            UserCategory.MEDICAL_PROFESSIONAL: "المهنيين الصحيين",
            UserCategory.ACADEMIC: "الأكاديميين",
            UserCategory.ENGINEER: "المهندسين",
            UserCategory.STUDENT: "الطلاب",
            UserCategory.FOREIGN_NATIONAL: "الأجانب",
            UserCategory.CIVIL_SERVANT: "موظفي الدولة",
            UserCategory.PRIVATE_SECTOR: "القطاع الخاص",
            UserCategory.GENERAL: "العامة"
        }
        return names.get(category, "العامة")
    
    def format_personalized_response(self, advice: PersonalizedAdvice) -> str:
        """Format personalized advice as user-friendly response"""
        lines = []
        
        # General answer
        lines.append(advice.general_answer)
        lines.append("")
        
        # Personalized insights
        if advice.personalized_insights:
            lines.append("👤 **نصائح مخصصة لك:**")
            for insight in advice.personalized_insights:
                lines.append(f"  {insight}")
            lines.append("")
        
        # Applicable exceptions
        if advice.applicable_exceptions:
            lines.append("⚖️ **استثناءات قد تنطبق عليك:**")
            for exception in advice.applicable_exceptions:
                lines.append(f"  {exception}")
            lines.append("")
        
        # Specific recommendations
        if advice.specific_recommendations:
            lines.append("💡 **توصيات محددة:**")
            for i, rec in enumerate(advice.specific_recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        # Relevant laws
        if advice.relevant_laws:
            lines.append("📚 **قوانين ذات صلة بوضعك:**")
            for law in advice.relevant_laws[:3]:
                lines.append(f"  • {law['law']}")
                if law.get("article"):
                    lines.append(f"    المادة {law['article']}")
            lines.append("")
        
        # Confidence note
        if advice.confidence < 0.7:
            lines.append("⚠️ **ملاحظة**: التخصيص يعتمد على معلومات محدودة. يُنصح بتقديم المزيد من التفاصيل.")
        
        return "\n".join(lines)
