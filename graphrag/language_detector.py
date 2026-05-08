from langdetect import detect, LangDetectException
from graphrag.models import Language
import re
import logging

logger = logging.getLogger(__name__)


class LanguageDetector:
    """Detect and handle multilingual input including Darija"""
    
    # Darija-specific patterns (Moroccan Arabic dialect)
    DARIJA_PATTERNS = [
        r'\b(واش|علاش|كيفاش|فين|شنو|شكون|فاش|منين|اش|شحال)\b',
        r'\b(بغيت|بغا|كنبغي|غادي|غير|بزاف|شوية|شويا)\b',
        r'\b(درابا|دابا|توا|باش|ديال|نتاع|متاع)\b',
        r'\b(مزيان|مليح|بصح|والاكين|ولكن|حيت|حتى)\b',
        r'\b(كاين|ماكاينش|راه|هاد|هادي|هادوك)\b',
    ]
    
    def __init__(self):
        self.darija_regex = re.compile('|'.join(self.DARIJA_PATTERNS), re.IGNORECASE)
    
    def detect_language(self, text: str) -> Language:
        """
        Detect language with Darija support
        
        Priority:
        1. Check for Darija patterns
        2. Use langdetect for standard languages
        3. Fallback to Arabic if has Arabic script
        """
        if not text or len(text.strip()) < 3:
            return Language.ARABIC
        
        # Check for Darija first
        if self._is_darija(text):
            logger.info("Detected Darija input")
            return Language.DARIJA
        
        try:
            lang_code = detect(text)
            
            if lang_code == 'ar':
                return Language.ARABIC
            elif lang_code == 'en':
                return Language.ENGLISH
            elif lang_code == 'fr':
                return Language.FRENCH
            else:
                # Check for Arabic script
                if self._has_arabic_script(text):
                    return Language.ARABIC
                return Language.ENGLISH
                
        except LangDetectException:
            logger.warning(f"Language detection failed for: {text[:50]}")
            if self._has_arabic_script(text):
                return Language.ARABIC
            return Language.ENGLISH
    
    def _is_darija(self, text: str) -> bool:
        """Check if text contains Darija-specific patterns"""
        return bool(self.darija_regex.search(text))
    
    def _has_arabic_script(self, text: str) -> bool:
        """Check if text contains Arabic characters"""
        arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
        return bool(arabic_pattern.search(text))
    
    def get_response_language(self, detected_lang: Language) -> Language:
        """
        Determine response language based on input
        
        Rule: If input is Darija, respond in Standard Arabic for formal accuracy
        Otherwise, respond in the same language
        """
        if detected_lang == Language.DARIJA:
            logger.info("Converting Darija input to Standard Arabic response")
            return Language.ARABIC
        return detected_lang
    
    def normalize_arabic(self, text: str) -> str:
        """Normalize Arabic text for better matching"""
        # Remove diacritics
        text = re.sub(r'[ًٌٍَُِّْـ]', '', text)
        # Normalize alef variants
        text = re.sub(r'[إأآا]', 'ا', text)
        # Normalize yaa
        text = re.sub(r'ى', 'ي', text)
        # Normalize taa marbouta
        text = re.sub(r'ة', 'ه', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
