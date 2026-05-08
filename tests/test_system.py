"""
Comprehensive system tests for GraphRAG
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from graphrag.language_detector import LanguageDetector
from graphrag.guardrails import Guardrails
from graphrag.models import Language, QueryRequest
import logging

logging.basicConfig(level=logging.INFO)


class TestLanguageDetection:
    """Test language detection including Darija"""
    
    def setup_method(self):
        self.detector = LanguageDetector()
    
    def test_arabic_detection(self):
        text = "ما هي شروط التوظيف في الوزارة؟"
        lang = self.detector.detect_language(text)
        assert lang == Language.ARABIC
    
    def test_english_detection(self):
        text = "What are the employment requirements?"
        lang = self.detector.detect_language(text)
        assert lang == Language.ENGLISH
    
    def test_french_detection(self):
        text = "Quelles sont les conditions d'emploi?"
        lang = self.detector.detect_language(text)
        assert lang == Language.FRENCH
    
    def test_darija_detection(self):
        # Darija-specific words
        text = "واش كاين شي شروط للخدمة؟"
        lang = self.detector.detect_language(text)
        assert lang == Language.DARIJA
    
    def test_darija_response_language(self):
        # Darija should respond in Standard Arabic
        detected = Language.DARIJA
        response_lang = self.detector.get_response_language(detected)
        assert response_lang == Language.ARABIC
    
    def test_arabic_normalization(self):
        text = "المَادَّةُ"
        normalized = self.detector.normalize_arabic(text)
        assert "َ" not in normalized  # No diacritics
        assert "ُ" not in normalized


class TestGuardrails:
    """Test safety and domain constraints"""
    
    def setup_method(self):
        self.guardrails = Guardrails()
    
    def test_legal_query_allowed(self):
        question = "ما هي شروط التوظيف في الوزارة؟"
        is_safe, reason = self.guardrails.check_query_safety(question, Language.ARABIC)
        assert is_safe is True
        assert reason is None
    
    def test_political_query_blocked(self):
        question = "ما رأيك في الحكومة السياسية؟"
        is_safe, reason = self.guardrails.check_query_safety(question, Language.ARABIC)
        assert is_safe is False
        assert reason == "political_topic"
    
    def test_violent_content_blocked(self):
        question = "كيف يمكن قتل شخص؟"
        is_safe, reason = self.guardrails.check_query_safety(question, Language.ARABIC)
        assert is_safe is False
        assert reason == "violent_content"
    
    def test_off_topic_blocked(self):
        question = "What is the weather today?"
        is_safe, reason = self.guardrails.check_query_safety(question, Language.ENGLISH)
        assert is_safe is False
        assert reason == "off_topic"
    
    def test_rejection_messages(self):
        # Test Arabic rejection message
        msg = self.guardrails.get_rejection_message("political_topic", Language.ARABIC)
        assert "نعتذر" in msg
        
        # Test English rejection message
        msg = self.guardrails.get_rejection_message("political_topic", Language.ENGLISH)
        assert "apologize" in msg.lower()


class TestModels:
    """Test Pydantic models"""
    
    def test_query_request_validation(self):
        # Valid request
        request = QueryRequest(
            question="ما هي شروط التوظيف؟",
            include_graph=True,
            max_results=5
        )
        assert request.question == "ما هي شروط التوظيف؟"
        assert request.max_results == 5
    
    def test_query_request_max_length(self):
        # Too long question
        with pytest.raises(Exception):
            QueryRequest(question="x" * 501)
    
    def test_query_request_defaults(self):
        request = QueryRequest(question="test")
        assert request.include_graph is True
        assert request.max_results == 5


class TestEntityExtraction:
    """Test entity extraction from Arabic text"""
    
    def test_law_extraction(self):
        from graphrag.graph_builder import GraphBuilder
        builder = GraphBuilder()
        
        text = "بموجب القانون رقم 12.20 الصادر في 2020"
        entities = builder.extract_entities_from_text(text, "Test", "2020")
        
        # Should extract law entity
        law_entities = [e for e in entities if e.entity_type == "Law"]
        assert len(law_entities) > 0
        assert "12.20" in law_entities[0].name
        
        builder.close()
    
    def test_article_extraction(self):
        from graphrag.graph_builder import GraphBuilder
        builder = GraphBuilder()
        
        text = "تنص المادة 5 على أن..."
        entities = builder.extract_entities_from_text(text, "Test", "2020")
        
        # Should extract article entity
        article_entities = [e for e in entities if e.entity_type == "Article"]
        assert len(article_entities) > 0
        
        builder.close()


class TestRetrievalFusion:
    """Test RRF (Reciprocal Rank Fusion)"""
    
    def test_rrf_calculation(self):
        from graphrag.retriever import HybridRetriever
        retriever = HybridRetriever()
        
        # Mock results
        vector_results = [
            ({"content": "doc1", "title": "Title 1"}, 0.9),
            ({"content": "doc2", "title": "Title 2"}, 0.8),
        ]
        
        graph_results = [
            {"content": "doc2", "title": "Title 2"},
            {"content": "doc3", "title": "Title 3"},
        ]
        
        # Apply RRF
        fused = retriever.reciprocal_rank_fusion(vector_results, graph_results, k=60)
        
        # doc2 should rank highest (appears in both)
        assert len(fused) == 3
        assert fused[0]["content"] == "doc2"


def run_integration_tests():
    """Run integration tests against live API"""
    import requests
    
    base_url = "http://localhost:8000"
    
    print("\n=== Integration Tests ===\n")
    
    # Test 1: Health check
    print("1. Testing health endpoint...")
    response = requests.get(f"{base_url}/health")
    assert response.status_code == 200
    print("✓ Health check passed")
    
    # Test 2: Arabic query
    print("\n2. Testing Arabic query...")
    response = requests.post(
        f"{base_url}/query",
        json={"question": "ما هي شروط التوظيف؟"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["detected_language"] == "ar"
    print(f"✓ Arabic query passed (cached: {data['cached']})")
    
    # Test 3: English query
    print("\n3. Testing English query...")
    response = requests.post(
        f"{base_url}/query",
        json={"question": "What are the employment requirements?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected_language"] == "en"
    print("✓ English query passed")
    
    # Test 4: Darija query (should respond in Arabic)
    print("\n4. Testing Darija query...")
    response = requests.post(
        f"{base_url}/query",
        json={"question": "واش كاين شي شروط للخدمة؟"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected_language"] == "darija"
    assert data["response_language"] == "ar"
    print("✓ Darija query passed (responds in Standard Arabic)")
    
    # Test 5: Political query (should be rejected)
    print("\n5. Testing political query rejection...")
    response = requests.post(
        f"{base_url}/query",
        json={"question": "ما رأيك في الحكومة؟"}
    )
    # Should still return 200 but with rejection message
    assert response.status_code == 200
    data = response.json()
    assert "نعتذر" in data["answer"] or "apologize" in data["answer"].lower()
    print("✓ Political query properly rejected")
    
    # Test 6: Cache stats
    print("\n6. Testing cache stats...")
    response = requests.get(f"{base_url}/cache/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_keys" in stats
    print(f"✓ Cache stats: {stats['total_keys']} keys, {stats.get('hit_rate', 0):.2%} hit rate")
    
    print("\n=== All Integration Tests Passed! ===\n")


if __name__ == "__main__":
    # Run unit tests
    pytest.main([__file__, "-v"])
    
    # Run integration tests (requires running API)
    try:
        run_integration_tests()
    except Exception as e:
        print(f"\n⚠️  Integration tests failed: {e}")
        print("Make sure the API is running: docker-compose up -d")
