"""
Run RAG Evaluation

Tests the RAG system with sample queries and evaluates performance
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from graphrag.rag_evaluator import RAGEvaluator
from graphrag.monitoring import PerformanceMonitor, QueryMetrics
import requests
import json
import time
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test cases for evaluation
TEST_CASES = [
    {
        "question": "ما هي شروط التوظيف في الوزارة؟",
        "language": "ar",
        "expected_topics": ["شروط", "توظيف", "مؤهلات"]
    },
    {
        "question": "What are the employment requirements?",
        "language": "en",
        "expected_topics": ["requirements", "employment", "qualifications"]
    },
    {
        "question": "Quelles sont les conditions d'emploi?",
        "language": "fr",
        "expected_topics": ["conditions", "emploi"]
    },
    {
        "question": "واش كاين شي شروط للخدمة؟",
        "language": "darija",
        "expected_response_lang": "ar"
    },
    {
        "question": "ما هي إجراءات التظلم؟",
        "language": "ar",
        "expected_topics": ["تظلم", "إجراءات"]
    }
]


def query_api(question: str, base_url: str = "http://localhost:8000") -> dict:
    """Query the API"""
    try:
        response = requests.post(
            f"{base_url}/query",
            json={"question": question},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"API query failed: {e}")
        return None


def evaluate_system():
    """Run comprehensive evaluation"""
    print("\n" + "="*60)
    print("RAG System Evaluation")
    print("="*60 + "\n")
    
    evaluator = RAGEvaluator()
    monitor = PerformanceMonitor()
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] Testing: {test_case['question'][:50]}...")
        
        # Query the API
        start_time = time.time()
        response = query_api(test_case['question'])
        query_time = (time.time() - start_time) * 1000
        
        if not response:
            print("  ✗ Query failed")
            continue
        
        # Extract response data
        answer = response.get('answer', '')
        detected_lang = response.get('detected_language', '')
        response_lang = response.get('response_language', '')
        cached = response.get('cached', False)
        processing_time = response.get('processing_time_ms', 0)
        citations = response.get('citations', [])
        
        # Print response info
        print(f"  Language: {detected_lang} → {response_lang}")
        print(f"  Cached: {cached}")
        print(f"  Time: {processing_time:.2f}ms")
        print(f"  Citations: {len(citations)}")
        
        # Verify language handling
        if test_case['language'] == 'darija':
            if response_lang == 'ar':
                print("  ✓ Darija → Arabic conversion working")
            else:
                print(f"  ✗ Expected Arabic response, got {response_lang}")
        
        # Record metrics
        metrics = QueryMetrics(
            query_id=f"test_{i}",
            question=test_case['question'],
            detected_language=detected_lang,
            response_language=response_lang,
            processing_time_ms=processing_time,
            cached=cached,
            retrieval_method=response.get('retrieval_method', 'unknown'),
            num_citations=len(citations),
            num_retrieved_docs=5  # Assuming default
        )
        monitor.record_query(metrics)
        
        # Evaluate RAG quality (if we have contexts)
        # Note: API doesn't return contexts, so we'll use citations as proxy
        if citations:
            contexts = [c.get('text_excerpt', '') for c in citations]
            
            try:
                eval_result = evaluator.evaluate(
                    question=test_case['question'],
                    answer=answer,
                    retrieved_contexts=contexts
                )
                
                print(f"\n  RAG Evaluation Scores:")
                print(f"    Faithfulness:       {eval_result.faithfulness:.3f}")
                print(f"    Answer Relevancy:   {eval_result.answer_relevancy:.3f}")
                print(f"    Context Relevancy:  {eval_result.context_relevancy:.3f}")
                print(f"    Context Precision:  {eval_result.context_precision:.3f}")
                print(f"    Context Recall:     {eval_result.context_recall:.3f}")
                print(f"    Overall Score:      {eval_result.overall_score:.3f}")
                
                results.append({
                    "test_case": i,
                    "question": test_case['question'][:50],
                    "metrics": eval_result.to_dict(),
                    "performance": {
                        "processing_time_ms": processing_time,
                        "cached": cached,
                        "num_citations": len(citations)
                    }
                })
            
            except Exception as e:
                logger.error(f"Evaluation failed: {e}")
                print(f"  ✗ Evaluation error: {e}")
    
    # Print summary
    print("\n" + "="*60)
    print("Evaluation Summary")
    print("="*60)
    
    summary = monitor.get_summary_stats()
    print(f"\nPerformance Metrics:")
    print(f"  Total Queries:        {summary['total_queries']}")
    print(f"  Cached Queries:       {summary['cached_queries']}")
    print(f"  Cache Hit Rate:       {summary['cache_hit_rate']:.1%}")
    print(f"  Avg Processing Time:  {summary['avg_processing_time_ms']:.2f}ms")
    print(f"  Recent Avg Time:      {summary['recent_avg_time_ms']:.2f}ms")
    
    print(f"\nLanguage Distribution:")
    for lang, count in summary['language_distribution'].items():
        print(f"  {lang}: {count}")
    
    if results:
        print(f"\nRAG Quality Metrics (Average):")
        avg_faithfulness = sum(r['metrics']['faithfulness'] for r in results) / len(results)
        avg_relevancy = sum(r['metrics']['answer_relevancy'] for r in results) / len(results)
        avg_context_rel = sum(r['metrics']['context_relevancy'] for r in results) / len(results)
        avg_precision = sum(r['metrics']['context_precision'] for r in results) / len(results)
        avg_recall = sum(r['metrics']['context_recall'] for r in results) / len(results)
        avg_overall = sum(r['metrics']['overall_score'] for r in results) / len(results)
        
        print(f"  Faithfulness:       {avg_faithfulness:.3f}")
        print(f"  Answer Relevancy:   {avg_relevancy:.3f}")
        print(f"  Context Relevancy:  {avg_context_rel:.3f}")
        print(f"  Context Precision:  {avg_precision:.3f}")
        print(f"  Context Recall:     {avg_recall:.3f}")
        print(f"  Overall Score:      {avg_overall:.3f}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = Path("./metrics") / f"evaluation_{timestamp}.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "test_cases": len(TEST_CASES),
            "performance_summary": summary,
            "rag_metrics": results,
            "system_info": monitor.get_performance_report()
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Results saved to: {results_file}")
    print("\n" + "="*60)


def test_cache_effectiveness():
    """Test cache effectiveness with repeated queries"""
    print("\n" + "="*60)
    print("Cache Effectiveness Test")
    print("="*60 + "\n")
    
    test_query = "ما هي شروط التوظيف في الوزارة؟"
    
    # First query (uncached)
    print("1. First query (should be uncached)...")
    response1 = query_api(test_query)
    if response1:
        print(f"   Time: {response1['processing_time_ms']:.2f}ms")
        print(f"   Cached: {response1['cached']}")
    
    time.sleep(1)
    
    # Second query (should be cached)
    print("\n2. Second query (should be cached)...")
    response2 = query_api(test_query)
    if response2:
        print(f"   Time: {response2['processing_time_ms']:.2f}ms")
        print(f"   Cached: {response2['cached']}")
    
    # Similar query (should be cached with semantic matching)
    print("\n3. Similar query (should be cached)...")
    similar_query = "ما هي الشروط للتوظيف؟"
    response3 = query_api(similar_query)
    if response3:
        print(f"   Time: {response3['processing_time_ms']:.2f}ms")
        print(f"   Cached: {response3['cached']}")
        if response3['cached']:
            print(f"   Similarity: {response3.get('similarity_score', 'N/A')}")
    
    # Calculate speedup
    if response1 and response2:
        speedup = response1['processing_time_ms'] / response2['processing_time_ms']
        print(f"\n✓ Cache speedup: {speedup:.1f}x faster")


def main():
    """Main evaluation routine"""
    print("\n" + "="*60)
    print("Ministry Regulation RAG System - Evaluation Suite")
    print("="*60)
    
    # Check if API is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("\n✗ API is not healthy. Please start the system first:")
            print("  python start_system.py")
            return
    except Exception as e:
        print("\n✗ Cannot connect to API. Please start the system first:")
        print("  python start_system.py")
        return
    
    print("\n✓ API is running\n")
    
    # Run evaluations
    try:
        # Test cache effectiveness
        test_cache_effectiveness()
        
        # Run full evaluation
        evaluate_system()
        
        print("\n✓ Evaluation complete!")
        print("\nNext steps:")
        print("  1. Review metrics in ./metrics/ directory")
        print("  2. Check cache stats: curl http://localhost:8000/cache/stats")
        print("  3. Fine-tune similarity threshold if needed")
        
    except KeyboardInterrupt:
        print("\n\nEvaluation interrupted by user")
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        print(f"\n✗ Evaluation failed: {e}")


if __name__ == "__main__":
    main()
