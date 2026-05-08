from typing import Tuple, Optional
from graphrag.models import Language
from graphrag.language_detector import LanguageDetector
import re
import logging

logger = logging.getLogger(__name__)


class Guardrails:
    """Safety and domain constraint enforcement"""
    
    # Political and sensitive topics to filter
    POLITICAL_TOPICS = {
        Language.ARABIC: [
            "فلسطين", "إسرائيل", "الصراع", "حزب الله", "حماس",
            "الجهاد الإسلامي", "الاحتلال", "المقاومة", "الانتفاضة",
            "الملك", "الحكومة السياسية", "الانتخابات", "المعارضة",
            "الاحتجاج", "المظاهرات", "الثورة", "الانقلاب"
        ],
        Language.ENGLISH: [
            "palestine", "israel", "gaza", "west bank", "hamas", "hezbollah",
            "occupation", "resistance", "uprising", "king", "political government",
            "elections", "opposition", "protest", "demonstration", "revolution", "coup"
        ],
        Language.FRENCH: [
            "palestine", "israël", "gaza", "cisjordanie", "hamas", "hezbollah",
            "occupation", "résistance", "soulèvement", "roi", "gouvernement politique",
            "élections", "opposition", "protestation", "manifestation", "révolution"
        ],
        Language.DARIJA: [
            "فلسطين", "إسرائيل", "الملك", "الحكومة", "المظاهرات"
        ]
    }
    
    # Violent or harmful content patterns
    VIOLENT_PATTERNS = {
        Language.ARABIC: [
            "قتل", "تفجير", "إرهاب", "عنف", "سلاح", "قنبلة",
            "اغتيال", "تدمير", "حرق", "هجوم"
        ],
        Language.ENGLISH: [
            "kill", "bomb", "terror", "violence", "weapon", "explosive",
            "assassination", "destroy", "burn", "attack"
        ],
        Language.FRENCH: [
            "tuer", "bombe", "terreur", "violence", "arme", "explosif",
            "assassinat", "détruire", "brûler", "attaque"
        ]
    }
    
    # Legal domain keywords (allowed topics)
    LEGAL_KEYWORDS = {
        Language.ARABIC: [
            "قانون", "مرسوم", "قرار", "لائحة", "نظام", "مادة",
            "فصل", "باب", "وزارة", "تنظيم", "إجراء", "شرط",
            "حق", "واجب", "التزام", "عقوبة", "جزاء"
        ],
        Language.ENGLISH: [
            "law", "decree", "decision", "regulation", "system", "article",
            "chapter", "section", "ministry", "organization", "procedure",
            "condition", "right", "duty", "obligation", "penalty", "sanction"
        ],
        Language.FRENCH: [
            "loi", "décret", "décision", "règlement", "système", "article",
            "chapitre", "section", "ministère", "organisation", "procédure",
            "condition", "droit", "devoir", "obligation", "pénalité", "sanction"
        ]
    }
    
    def __init__(self):
        self.lang_detector = LanguageDetector()
    
    def check_query_safety(self, question: str, detected_lang: Language) -> Tuple[bool, Optional[str]]:
        """
        Check if query is safe and within domain
        
        Returns:
            (is_safe, reason) - reason is None if safe
        """
        normalized = self.lang_detector.normalize_arabic(question).lower()
        
        # Check for political topics
        if self._contains_political_content(normalized, detected_lang):
            return False, "political_topic"
        
        # Check for violent content
        if self._contains_violent_content(normalized, detected_lang):
            return False, "violent_content"
        
        # Check if query is too vague or off-topic
        if not self._is_legal_domain(normalized, detected_lang):
            return False, "off_topic"
        
        return True, None
    
    def _contains_political_content(self, text: str, lang: Language) -> bool:
        """Check for political or sensitive topics"""
        topics = self.POLITICAL_TOPICS.get(lang, [])
        for topic in topics:
            normalized_topic = self.lang_detector.normalize_arabic(topic).lower()
            if normalized_topic in text:
                logger.warning(f"Political content detected: {topic}")
                return True
        return False
    
    def _contains_violent_content(self, text: str, lang: Language) -> bool:
        """Check for violent or harmful content"""
        patterns = self.VIOLENT_PATTERNS.get(lang, [])
        for pattern in patterns:
            normalized_pattern = self.lang_detector.normalize_arabic(pattern).lower()
            if normalized_pattern in text:
                logger.warning(f"Violent content detected: {pattern}")
                return True
        return False
    
    def _is_legal_domain(self, text: str, lang: Language) -> bool:
        """Check if query is related to legal domain"""
        keywords = self.LEGAL_KEYWORDS.get(lang, [])
        
        # If text is very short, be lenient
        if len(text.split()) < 3:
            return True
        
        # Check if at least one legal keyword is present
        for keyword in keywords:
            normalized_keyword = self.lang_detector.normalize_arabic(keyword).lower()
            if normalized_keyword in text:
                return True
        
        # If no legal keywords found, might be off-topic
        logger.info(f"No legal keywords found in query: {text[:50]}")
        return False
    
    def get_rejection_message(self, reason: str, lang: Language) -> str:
        """Get appropriate rejection message based on reason and language"""
        messages = {
            "political_topic": {
                Language.ARABIC: "نعتذر، لا يمكننا معالجة الأسئلة المتعلقة بالمواضيع السياسية الحساسة. يرجى طرح أسئلة تتعلق بالقوانين واللوائح الوزارية.",
                Language.ENGLISH: "We apologize, we cannot process questions about sensitive political topics. Please ask questions related to laws and ministry regulations.",
                Language.FRENCH: "Nous nous excusons, nous ne pouvons pas traiter les questions sur des sujets politiques sensibles. Veuillez poser des questions liées aux lois et règlements ministériels.",
                Language.DARIJA: "سماح لينا، ماقادرينش نجاوبو على الأسئلة السياسية. عافاك سول على القوانين والأنظمة."
            },
            "violent_content": {
                Language.ARABIC: "نعتذر، لا يمكننا معالجة هذا النوع من الاستفسارات. نظامنا مخصص للأسئلة القانونية فقط.",
                Language.ENGLISH: "We apologize, we cannot process this type of inquiry. Our system is dedicated to legal questions only.",
                Language.FRENCH: "Nous nous excusons, nous ne pouvons pas traiter ce type de demande. Notre système est dédié aux questions juridiques uniquement.",
                Language.DARIJA: "سماح لينا، ماقادرينش نجاوبو على هاد النوع ديال الأسئلة."
            },
            "off_topic": {
                Language.ARABIC: "يبدو أن سؤالك لا يتعلق بالقوانين واللوائح الوزارية. يرجى طرح أسئلة قانونية محددة.",
                Language.ENGLISH: "Your question doesn't seem to be related to laws and ministry regulations. Please ask specific legal questions.",
                Language.FRENCH: "Votre question ne semble pas liée aux lois et règlements ministériels. Veuillez poser des questions juridiques spécifiques.",
                Language.DARIJA: "السؤال ديالك ماشي على القوانين. عافاك سول على حاجة قانونية."
            }
        }
        
        return messages.get(reason, {}).get(lang, messages[reason][Language.ARABIC])
    
    def validate_citation_requirement(self, answer: str, citations: list) -> bool:
        """Ensure answer has proper citations"""
        if not citations or len(citations) == 0:
            logger.warning("Answer generated without citations")
            return False
        return True
