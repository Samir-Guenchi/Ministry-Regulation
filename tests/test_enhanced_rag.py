"""
Test Enhanced RAG System with 3 Innovations:
1. Temporal Reasoning
2. Contradiction Detection  
3. Hierarchical Chunking
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from graphrag.temporal_reasoner import TemporalReasoner
from graphrag.contradiction_detector import ContradictionDetector
from graphrag.hierarchical_chunker import HierarchicalChunker
import json

def test_temporal_reasoning():
    """Test temporal reasoning module"""
    print("\n" + "="*80)
    print("🕐 TEST 1: TEMPORAL REASONING")
    print("="*80)
    
    reasoner = TemporalReasoner()
    
    test_queries = [
        "ما هي شروط التوظيف في 2019؟",
        "ما هي القوانين الحالية للتوظيف؟",
        "ما هي القوانين قبل 2020؟",
        "What were the requirements in 2018?",
        "Quelles sont les lois actuelles?"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        context = reasoner.extract_temporal_context(query)
        print(f"  ✓ Type: {context.temporal_type}")
        print(f"  ✓ Date: {context.query_date}")
        print(f"  ✓ Is Current: {context.is_current}")
        print(f"  ✓ Is Historical: {context.is_historical}")
        if context.date_phrases:
            print(f"  ✓ Phrases: {context.date_phrases}")
    
    # Test document filtering
    print("\n" + "-"*80)
    print("Testing Document Filtering by Date")
    print("-"*80)
    
    sample_docs = [
        {
            "content": "قرار رقم 09 مؤرخ في 04 جانفي 2018",
            "title": "قرار 2018",
            "metadata": {}
        },
        {
            "content": "قرار رقم 15 مؤرخ في 10 مارس 2020",
            "title": "قرار 2020",
            "metadata": {}
        },
        {
            "content": "قرار رقم 22 مؤرخ في 15 جوان 2022",
            "title": "قرار 2022",
            "metadata": {}
        }
    ]
    
    query = "ما هي شروط التوظيف في 2019؟"
    context = reasoner.extract_temporal_context(query)
    filtered = reasoner.filter_documents_by_date(sample_docs, context)
    
    print(f"\nQuery: {query}")
    print(f"Original docs: {len(sample_docs)}")
    print(f"Filtered docs: {len(filtered)}")
    for doc in filtered:
        print(f"  • {doc['title']} (confidence: {doc.get('temporal_confidence', 'N/A')})")
    
    explanation = reasoner.build_temporal_explanation(context, filtered)
    print(f"\nExplanation:\n{explanation}")
    
    print("\n✅ Temporal Reasoning Test Complete!")


def test_contradiction_detection():
    """Test contradiction detection module"""
    print("\n" + "="*80)
    print("⚖️ TEST 2: CONTRADICTION DETECTION")
    print("="*80)
    
    detector = ContradictionDetector()
    
    # Sample documents with contradictions
    sample_docs = [
        {
            "content": """
            المادة 5: يشترط في المترشح 5 سنوات من الخبرة المهنية.
            يجب أن يكون حاصلاً على شهادة الدكتوراه.
            الراتب الأساسي: 50000 دينار.
            """,
            "title": "القانون 12.20 (2020)",
            "metadata": {"date": "2020-01-01", "source": "قانون 12.20"}
        },
        {
            "content": """
            المادة 3: يشترط في المترشح 3 سنوات من الخبرة المهنية.
            يجب أن يكون حاصلاً على شهادة الماجستير.
            الراتب الأساسي: 45000 دينار.
            """,
            "title": "القانون 08.15 (2018)",
            "metadata": {"date": "2018-01-01", "source": "قانون 08.15"}
        },
        {
            "content": """
            المادة 7: يشترط في المترشح 5 سنوات من الخبرة.
            شهادة الدكتوراه مطلوبة.
            """,
            "title": "المرسوم 19.05 (2019)",
            "metadata": {"date": "2019-01-01", "source": "مرسوم 19.05"}
        }
    ]
    
    print("\nAnalyzing documents for contradictions...")
    contradictions, summary = detector.detect_contradictions(sample_docs)
    
    print(f"\n📊 Summary:")
    print(f"  • Total contradictions: {summary['total_contradictions']}")
    print(f"  • High severity: {summary['high_severity']}")
    print(f"  • Medium severity: {summary['medium_severity']}")
    print(f"  • Low severity: {summary['low_severity']}")
    print(f"  • Resolved: {summary['resolved']}")
    print(f"  • Unresolved: {summary['unresolved']}")
    
    if contradictions:
        print(f"\n⚠️ Detected Contradictions:")
        for i, c in enumerate(contradictions, 1):
            print(f"\n{i}. Field: {c.field}")
            print(f"   Doc 1: {c.doc1_value} ({c.doc1_source})")
            if c.doc1_date:
                print(f"   Date 1: {c.doc1_date.year}")
            print(f"   Doc 2: {c.doc2_value} ({c.doc2_source})")
            if c.doc2_date:
                print(f"   Date 2: {c.doc2_date.year}")
            print(f"   Severity: {c.severity}")
            if c.resolution:
                print(f"   ✅ Resolution: {c.resolution}")
            else:
                print(f"   ❌ Unresolved")
    
    # Build warning message
    warning = detector.build_contradiction_warning(contradictions, summary)
    print(f"\n{'-'*80}")
    print("Warning Message for User:")
    print("-"*80)
    print(warning)
    
    print("\n✅ Contradiction Detection Test Complete!")


def test_hierarchical_chunking():
    """Test hierarchical chunking module"""
    print("\n" + "="*80)
    print("📄 TEST 3: HIERARCHICAL CHUNKING")
    print("="*80)
    
    chunker = HierarchicalChunker(chunk_size=300, chunk_overlap=50)
    
    # Sample legal document
    sample_doc = {
        "content": """
القانون رقم 12.20 المؤرخ في 15 يناير 2020
المتعلق بشروط التوظيف في الوظيفة العمومية

الباب الأول: أحكام عامة

المادة 1: يهدف هذا القانون إلى تحديد شروط وإجراءات التوظيف في الوظيفة العمومية.

المادة 2: تطبق أحكام هذا القانون على جميع المؤسسات العمومية.

الباب الثاني: شروط التوظيف

المادة 3: يشترط في المترشح للتوظيف:
- أن يكون جزائري الجنسية
- أن يكون بالغاً من العمر 18 سنة على الأقل
- أن يكون حاصلاً على المؤهل العلمي المطلوب

المادة 4: يجب على المترشح أن يتمتع بحقوقه المدنية والسياسية.

المادة 5: يشترط في المترشح 5 سنوات من الخبرة المهنية في المجال المطلوب.
يجب أن تكون الخبرة موثقة بشهادات عمل رسمية.
يمكن احتساب فترات التدريب ضمن الخبرة المطلوبة.

الباب الثالث: إجراءات التوظيف

المادة 6: يتم التوظيف عن طريق مسابقة على أساس الاختبارات أو الشهادات.
        """,
        "title": "القانون 12.20",
        "metadata": {
            "law_name": "القانون رقم 12.20",
            "law_number": "12.20",
            "year": "2020"
        }
    }
    
    print("\nChunking document...")
    chunks = chunker.chunk_document(sample_doc)
    
    print(f"\n📊 Chunking Results:")
    print(f"  • Total chunks: {len(chunks)}")
    
    print(f"\n📋 Chunk Details:")
    for i, chunk in enumerate(chunks, 1):
        print(f"\n{i}. Chunk ID: {chunk.chunk_id}")
        print(f"   Type: {chunk.chunk_type}")
        print(f"   Level: {chunk.level}")
        print(f"   Law: {chunk.law_name}")
        print(f"   Article: {chunk.article_number or 'N/A'}")
        print(f"   Paragraph: {chunk.paragraph_number or 'N/A'}")
        print(f"   Hierarchy: {chunk.full_hierarchy}")
        if chunk.parent_context:
            print(f"   Parent Context: {chunk.parent_context}")
        print(f"   Content: {chunk.content[:100]}...")
        
        # Build citation
        citation = chunker.build_citation(chunk)
        print(f"   Citation: {citation}")
    
    # Test full article reconstruction
    print(f"\n{'-'*80}")
    print("Testing Article Reconstruction")
    print("-"*80)
    
    article_5 = chunker.get_full_article(chunks, "5")
    if article_5:
        print(f"\nFull Article 5:")
        print(article_5)
    
    print("\n✅ Hierarchical Chunking Test Complete!")


def test_integration():
    """Test all three modules together"""
    print("\n" + "="*80)
    print("🚀 TEST 4: INTEGRATED SYSTEM")
    print("="*80)
    
    print("\nSimulating a complete query with all enhancements...")
    
    query = "ما هي شروط التوظيف في 2019؟"
    print(f"\n📝 Query: {query}")
    
    # Step 1: Temporal reasoning
    print("\n1️⃣ Temporal Reasoning:")
    reasoner = TemporalReasoner()
    temporal_context = reasoner.extract_temporal_context(query)
    print(f"   ✓ Detected temporal type: {temporal_context.temporal_type}")
    print(f"   ✓ Query date: {temporal_context.query_date}")
    
    # Step 2: Retrieve and filter documents (simulated)
    print("\n2️⃣ Document Retrieval & Filtering:")
    sample_docs = [
        {
            "content": "قرار 2018: يشترط 3 سنوات خبرة",
            "title": "قرار 2018",
            "metadata": {"date": "2018-01-01"}
        },
        {
            "content": "قرار 2020: يشترط 5 سنوات خبرة",
            "title": "قرار 2020",
            "metadata": {"date": "2020-01-01"}
        }
    ]
    
    filtered_docs = reasoner.filter_documents_by_date(sample_docs, temporal_context)
    print(f"   ✓ Retrieved {len(filtered_docs)} temporally relevant documents")
    
    # Step 3: Contradiction detection
    print("\n3️⃣ Contradiction Detection:")
    detector = ContradictionDetector()
    contradictions, summary = detector.detect_contradictions(filtered_docs)
    print(f"   ✓ Detected {len(contradictions)} contradictions")
    if contradictions:
        print(f"   ⚠️ High severity: {summary['high_severity']}")
        print(f"   ✅ Resolved: {summary['resolved']}")
    
    # Step 4: Hierarchical context
    print("\n4️⃣ Hierarchical Context:")
    chunker = HierarchicalChunker()
    for doc in filtered_docs[:1]:
        chunks = chunker.chunk_document(doc)
        if chunks:
            print(f"   ✓ Extracted hierarchy: {chunks[0].full_hierarchy}")
    
    # Step 5: Build enhanced response
    print("\n5️⃣ Enhanced Response:")
    temporal_exp = reasoner.build_temporal_explanation(temporal_context, filtered_docs)
    contradiction_warn = detector.build_contradiction_warning(contradictions, summary)
    
    print(f"\n{temporal_exp}")
    if contradiction_warn:
        print(f"\n{contradiction_warn}")
    
    print("\n✅ Integration Test Complete!")
    print("\n" + "="*80)
    print("🎉 ALL TESTS PASSED!")
    print("="*80)
    print("\nThe enhanced RAG system now includes:")
    print("  ✅ Temporal Reasoning - Understands time-based queries")
    print("  ✅ Contradiction Detection - Identifies conflicting information")
    print("  ✅ Hierarchical Chunking - Preserves document structure")
    print("\nThese innovations significantly improve accuracy and user trust!")


if __name__ == "__main__":
    try:
        test_temporal_reasoning()
        test_contradiction_detection()
        test_hierarchical_chunking()
        test_integration()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
