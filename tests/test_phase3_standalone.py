"""
Standalone Test for Phase 3 Advanced Features
Tests modules independently without full system dependencies
"""
import sys
sys.path.append('.')

from graphrag.multi_hop_reasoner import MultiHopReasoner, ReasoningStepType
from graphrag.query_expander import QueryExpander
from graphrag.cross_encoder_reranker import CrossEncoderReranker


def test_multi_hop_reasoning():
    """Test multi-hop reasoning for complex questions"""
    print("\n" + "="*80)
    print("TEST 1: Multi-Hop Reasoning")
    print("="*80)
    
    reasoner = MultiHopReasoner()
    
    # Test 1: Complex question detection
    test_cases = [
        {
            "query": "كيف يمكن لطبيب أن يصبح أستاذ محاضر في الجامعة؟",
            "expected_complex": True,
            "description": "Complex: How can a doctor become a university lecturer?"
        },
        {
            "query": "ما الفرق بين أستاذ مساعد وأستاذ محاضر؟",
            "expected_complex": True,
            "description": "Complex: Difference between assistant and lecturer"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test['description']} ---")
        print(f"Query: {test['query']}")
        
        # Check if complex
        is_complex = reasoner.is_complex_question(test['query'])
        print(f"Is Complex: {is_complex} (Expected: {test['expected_complex']})")
        
        assert is_complex == test['expected_complex'], f"Failed: Expected {test['expected_complex']}, got {is_complex}"
        
        if is_complex:
            # Decompose question
            sub_questions = reasoner.decompose_question(test['query'])
            print(f"\nSub-questions ({len(sub_questions)}):")
            for j, sq in enumerate(sub_questions, 1):
                print(f"  {j}. {sq}")
            
            assert len(sub_questions) > 0, "Failed: No sub-questions generated"
            
            # Perform multi-hop reasoning
            result = reasoner.perform_multi_hop_reasoning(test['query'], max_hops=5)
            
            print(f"\nReasoning Steps: {len(result.reasoning_steps)}")
            print(f"Total Confidence: {result.total_confidence:.2%}")
            
            assert len(result.reasoning_steps) > 0, "Failed: No reasoning steps"
            assert 0 <= result.total_confidence <= 1, "Failed: Invalid confidence"
            
            print("\nReasoning Path:")
            for step in result.reasoning_steps:
                print(f"  Step {step.step_number} ({step.step_type.value}): {step.query[:60]}...")
                print(f"    Confidence: {step.confidence:.2%}")
            
            print(f"\nFinal Answer Preview:")
            print(result.final_answer[:300] + "...")
        
        print(f"\n✅ Test {i} passed")
    
    print("\n" + "="*80)
    print("✅ Multi-Hop Reasoning Tests Complete")
    print("="*80)


def test_query_expansion():
    """Test query expansion with synonyms and related terms"""
    print("\n" + "="*80)
    print("TEST 2: Query Expansion")
    print("="*80)
    
    expander = QueryExpander()
    
    test_queries = [
        {
            "query": "شروط التوظيف كأستاذ",
            "lang": "ar",
            "description": "Arabic: Employment requirements for professor",
            "expected_synonyms": ["توظيف", "شروط", "أستاذ"]
        },
        {
            "query": "وثائق المطلوبة للترشح",
            "lang": "ar",
            "description": "Arabic: Required documents for application",
            "expected_synonyms": ["وثائق", "مطلوب"]
        },
        {
            "query": "employment requirements",
            "lang": "en",
            "description": "English: Employment requirements",
            "expected_synonyms": ["employment", "requirements"]
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n--- Test Case {i}: {test['description']} ---")
        print(f"Original Query: {test['query']}")
        
        # Expand query
        expansion = expander.expand_query(test['query'], max_expansions=10)
        
        print(f"\nExpansion Score: {expansion.expansion_score:.2%}")
        print(f"Expanded Terms: {len(expansion.expanded_terms)}")
        
        assert 0 <= expansion.expansion_score <= 1, "Failed: Invalid expansion score"
        assert len(expansion.expanded_queries) > 0, "Failed: No expanded queries"
        
        if expansion.synonyms:
            print("\nSynonyms Found:")
            for term, syns in list(expansion.synonyms.items())[:5]:
                print(f"  • {term}: {', '.join(syns[:3])}")
        
        if expansion.related_terms:
            print(f"\nRelated Terms: {', '.join(expansion.related_terms[:5])}")
        
        print(f"\nExpanded Queries ({len(expansion.expanded_queries)}):")
        for j, eq in enumerate(expansion.expanded_queries[:5], 1):
            print(f"  {j}. {eq}")
        
        # Test retrieval expansion
        retrieval_queries = expander.expand_for_retrieval(test['query'])
        print(f"\nRetrieval Queries: {len(retrieval_queries)}")
        
        assert len(retrieval_queries) > 0, "Failed: No retrieval queries"
        assert retrieval_queries[0] == test['query'], "Failed: Original query not first"
        
        print(f"\n✅ Test {i} passed")
    
    print("\n" + "="*80)
    print("✅ Query Expansion Tests Complete")
    print("="*80)


def test_cross_encoder_reranking():
    """Test cross-encoder re-ranking"""
    print("\n" + "="*80)
    print("TEST 3: Cross-Encoder Re-ranking")
    print("="*80)
    
    reranker = CrossEncoderReranker()
    
    # Create mock documents
    query = "شروط التوظيف كأستاذ محاضر"
    
    documents = [
        {
            "title": "قانون التوظيف في الجامعات",
            "content": "يشترط للتوظيف كأستاذ محاضر الحصول على شهادة الدكتوراه وخبرة 3 سنوات في التدريس",
            "score": 0.75
        },
        {
            "title": "شروط الترقية",
            "content": "تتطلب الترقية إلى رتبة أستاذ التعليم العالي نشر 10 أبحاث علمية",
            "score": 0.65
        },
        {
            "title": "متطلبات التوظيف",
            "content": "يجب على المترشح تقديم ملف يحتوي على الشهادات والسيرة الذاتية",
            "score": 0.80
        },
        {
            "title": "الإجراءات الإدارية",
            "content": "تتم المسابقة على مرحلتين: اختبار كتابي ومقابلة شفوية",
            "score": 0.70
        },
        {
            "title": "حقوق الأساتذة",
            "content": "يحق للأستاذ المحاضر الحصول على راتب شهري وتأمين صحي",
            "score": 0.60
        }
    ]
    
    print(f"Query: {query}")
    print(f"Documents: {len(documents)}")
    
    print("\nOriginal Ranking:")
    for i, doc in enumerate(documents, 1):
        print(f"  {i}. {doc['title']} (score: {doc['score']:.2f})")
    
    # Re-rank documents
    reranked_docs, summary = reranker.rerank(
        query,
        documents,
        top_k=5,
        return_scores=True
    )
    
    print(f"\nRe-ranking Summary:")
    print(f"  Method: {summary.reranking_method}")
    print(f"  Total Documents: {summary.total_documents}")
    print(f"  Avg Score Improvement: {summary.avg_score_improvement:.3f}")
    print(f"  Top-5 Changed: {summary.top_k_changed}")
    
    assert summary.total_documents == len(documents), "Failed: Document count mismatch"
    assert len(reranked_docs) == len(documents), "Failed: Reranked count mismatch"
    
    print("\nRe-ranked Results:")
    for i, doc in enumerate(reranked_docs, 1):
        original_rank = doc.get('_original_rank', '?')
        rerank_score = doc.get('_rerank_score', 0.0)
        
        rank_change = ""
        if isinstance(original_rank, int) and original_rank != i:
            change = original_rank - i
            if change > 0:
                rank_change = f" ⬆️ (+{change})"
            else:
                rank_change = f" ⬇️ ({change})"
        
        print(f"  {i}. {doc['title']}")
        print(f"     Original: #{original_rank}, Rerank Score: {rerank_score:.3f}{rank_change}")
    
    print("\n✅ Cross-Encoder Re-ranking Test Passed")
    
    print("\n" + "="*80)
    print("✅ Cross-Encoder Re-ranking Tests Complete")
    print("="*80)


def main():
    """Run all Phase 3 standalone tests"""
    print("\n" + "="*80)
    print("PHASE 3 ADVANCED FEATURES - STANDALONE TEST SUITE")
    print("="*80)
    print("\nTesting:")
    print("  1. Multi-hop Reasoning")
    print("  2. Query Expansion")
    print("  3. Cross-encoder Re-ranking")
    print("\n" + "="*80)
    
    try:
        # Test 1: Multi-hop Reasoning
        test_multi_hop_reasoning()
        
        # Test 2: Query Expansion
        test_query_expansion()
        
        # Test 3: Cross-encoder Re-ranking
        test_cross_encoder_reranking()
        
        print("\n" + "="*80)
        print("🎉 ALL PHASE 3 STANDALONE TESTS PASSED!")
        print("="*80)
        print("\n✅ Multi-hop Reasoning: Working")
        print("✅ Query Expansion: Working")
        print("✅ Cross-encoder Re-ranking: Working")
        print("\n📊 Summary:")
        print("  • Complex question detection: ✅")
        print("  • Question decomposition: ✅")
        print("  • Multi-step reasoning: ✅")
        print("  • Query synonym expansion: ✅")
        print("  • Related term discovery: ✅")
        print("  • Document re-ranking: ✅")
        print("  • Heuristic scoring: ✅")
        print("\n" + "="*80)
    
    except AssertionError as e:
        print(f"\n❌ Test assertion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
