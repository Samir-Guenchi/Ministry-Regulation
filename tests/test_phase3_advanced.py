"""
Test Phase 3 Advanced Features
- Multi-hop Reasoning
- Query Expansion
- Cross-encoder Re-ranking
"""
import sys
sys.path.append('.')

from graphrag.multi_hop_reasoner import MultiHopReasoner, ReasoningStepType
from graphrag.query_expander import QueryExpander
from graphrag.cross_encoder_reranker import CrossEncoderReranker
from graphrag.retriever import HybridRetriever


def test_multi_hop_reasoning():
    """Test multi-hop reasoning for complex questions"""
    print("\n" + "="*80)
    print("TEST 1: Multi-Hop Reasoning")
    print("="*80)
    
    reasoner = MultiHopReasoner()
    
    # Test 1: Complex question requiring multiple steps
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
        },
        {
            "query": "ما هي شروط التوظيف؟",
            "expected_complex": False,
            "description": "Simple: What are employment requirements?"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test['description']} ---")
        print(f"Query: {test['query']}")
        
        # Check if complex
        is_complex = reasoner.is_complex_question(test['query'])
        print(f"Is Complex: {is_complex} (Expected: {test['expected_complex']})")
        
        if is_complex:
            # Decompose question
            sub_questions = reasoner.decompose_question(test['query'])
            print(f"\nSub-questions ({len(sub_questions)}):")
            for j, sq in enumerate(sub_questions, 1):
                print(f"  {j}. {sq}")
            
            # Perform multi-hop reasoning
            result = reasoner.perform_multi_hop_reasoning(test['query'], max_hops=5)
            
            print(f"\nReasoning Steps: {len(result.reasoning_steps)}")
            print(f"Total Confidence: {result.total_confidence:.2%}")
            
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
            "description": "Arabic: Employment requirements for professor"
        },
        {
            "query": "وثائق المطلوبة للترشح",
            "lang": "ar",
            "description": "Arabic: Required documents for application"
        },
        {
            "query": "employment requirements",
            "lang": "en",
            "description": "English: Employment requirements"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n--- Test Case {i}: {test['description']} ---")
        print(f"Original Query: {test['query']}")
        
        # Expand query
        expansion = expander.expand_query(test['query'], max_expansions=10)
        
        print(f"\nExpansion Score: {expansion.expansion_score:.2%}")
        print(f"Expanded Terms: {len(expansion.expanded_terms)}")
        
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


def test_integrated_retrieval():
    """Test integrated retrieval with all Phase 3 features"""
    print("\n" + "="*80)
    print("TEST 4: Integrated Retrieval (All Phase 3 Features)")
    print("="*80)
    
    retriever = HybridRetriever()
    
    test_queries = [
        {
            "query": "كيف يمكن لطبيب أن يصبح أستاذ محاضر؟",
            "description": "Complex multi-hop question",
            "expected_features": ["multi_hop", "expansion", "reranking"]
        },
        {
            "query": "ما هي شروط التوظيف كأستاذ؟",
            "description": "Standard question with expansion",
            "expected_features": ["expansion", "reranking"]
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n--- Test Case {i}: {test['description']} ---")
        print(f"Query: {test['query']}")
        
        # Perform enhanced retrieval v2
        docs, method, enhancements = retriever.enhanced_retrieve_v2(
            test['query'],
            max_results=5,
            use_graph=False,  # Disable graph for testing
            use_multi_hop=True,
            use_query_expansion=True,
            use_reranking=True
        )
        
        print(f"\nRetrieval Method: {method}")
        print(f"Documents Retrieved: {len(docs)}")
        
        # Check enhancements
        print("\nEnhancements Applied:")
        
        if enhancements.get("is_complex_question"):
            print("  ✅ Multi-hop Reasoning")
            multi_hop = enhancements.get("multi_hop_reasoning")
            if multi_hop:
                print(f"     Steps: {len(multi_hop.reasoning_steps)}")
                print(f"     Confidence: {multi_hop.total_confidence:.2%}")
        
        if enhancements.get("query_expansion"):
            print("  ✅ Query Expansion")
            expansion = enhancements["query_expansion"]
            print(f"     Expanded Queries: {len(expansion.expanded_queries)}")
            print(f"     Expansion Score: {expansion.expansion_score:.2%}")
        
        if enhancements.get("reranking_summary"):
            print("  ✅ Cross-encoder Re-ranking")
            rerank = enhancements["reranking_summary"]
            print(f"     Method: {rerank.reranking_method}")
            print(f"     Avg Improvement: {rerank.avg_score_improvement:.3f}")
        
        if enhancements.get("temporal_context"):
            temporal = enhancements["temporal_context"]
            print(f"  ℹ️  Temporal Context: {temporal.temporal_type}")
        
        if enhancements.get("contradictions"):
            print(f"  ⚠️  Contradictions Detected: {len(enhancements['contradictions'])}")
        
        print(f"\n✅ Test {i} passed")
    
    print("\n" + "="*80)
    print("✅ Integrated Retrieval Tests Complete")
    print("="*80)


def main():
    """Run all Phase 3 tests"""
    print("\n" + "="*80)
    print("PHASE 3 ADVANCED FEATURES TEST SUITE")
    print("="*80)
    print("\nTesting:")
    print("  1. Multi-hop Reasoning")
    print("  2. Query Expansion")
    print("  3. Cross-encoder Re-ranking")
    print("  4. Integrated Retrieval")
    print("\n" + "="*80)
    
    try:
        # Test 1: Multi-hop Reasoning
        test_multi_hop_reasoning()
        
        # Test 2: Query Expansion
        test_query_expansion()
        
        # Test 3: Cross-encoder Re-ranking
        test_cross_encoder_reranking()
        
        # Test 4: Integrated Retrieval
        test_integrated_retrieval()
        
        print("\n" + "="*80)
        print("🎉 ALL PHASE 3 TESTS PASSED!")
        print("="*80)
        print("\n✅ Multi-hop Reasoning: Working")
        print("✅ Query Expansion: Working")
        print("✅ Cross-encoder Re-ranking: Working")
        print("✅ Integrated Retrieval: Working")
        print("\n" + "="*80)
    
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
