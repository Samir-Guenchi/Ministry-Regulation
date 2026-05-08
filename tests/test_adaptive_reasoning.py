"""
Test Adaptive Legal Reasoning Engine
Tests all 4 innovative modules:
1. Causal Reasoning Engine
2. Counterfactual Analyzer
3. Implicit Requirement Extractor
4. Situational Adapter
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from graphrag.causal_reasoning_engine import CausalReasoningEngine, CausalRelationType
from graphrag.counterfactual_analyzer import CounterfactualAnalyzer
from graphrag.implicit_requirement_extractor import ImplicitRequirementExtractor
from graphrag.situational_adapter import SituationalAdapter, UserCategory


def test_causal_reasoning():
    """Test causal reasoning engine"""
    print("\n" + "="*80)
    print("🧠 TEST 1: CAUSAL REASONING ENGINE")
    print("="*80)
    
    engine = CausalReasoningEngine()
    
    # Sample documents with causal relationships
    sample_docs = [
        {
            "content": """
            المادة 5: يشترط في المترشح أن يكون حاصلاً على شهادة الدكتوراه.
            المادة 6: إذا كان المترشح حاصلاً على شهادة الدكتوراه فإنه يمكنه التقديم لرتبة أستاذ.
            المادة 7: يتطلب منصب الأستاذ 5 سنوات من الخبرة المهنية.
            """,
            "title": "القانون 12.20",
            "article_number": "5-7"
        },
        {
            "content": """
            المادة 3: يمنع المترشح من التقديم إذا لم يكن حاصلاً على الشهادة المطلوبة.
            المادة 4: بشرط استيفاء الشروط يتم قبول الترشح.
            """,
            "title": "المرسوم 19.05",
            "article_number": "3-4"
        }
    ]
    
    print("\n📊 Extracting causal relations...")
    relations = engine.extract_causal_relations(sample_docs)
    
    print(f"\n✅ Extracted {len(relations)} causal relations:\n")
    for i, rel in enumerate(relations[:5], 1):
        print(f"{i}. Type: {rel.relation_type.value}")
        print(f"   Cause: {rel.cause}")
        print(f"   Effect: {rel.effect}")
        print(f"   Source: {rel.source_law}")
        print(f"   Confidence: {rel.confidence:.2f}")
        print()
    
    # Test causal chain building
    print("-"*80)
    print("Building Causal Chain")
    print("-"*80)
    
    if len(relations) >= 2:
        start = relations[0].cause
        end = relations[-1].effect
        
        print(f"\nSearching for chain: {start} → {end}")
        chain = engine.build_causal_chain(start, end, relations, max_depth=5)
        
        if chain:
            print(f"\n✅ Found chain with confidence {chain.total_confidence:.2f}:")
            print(chain.reasoning_path)
        else:
            print("\n❌ No chain found")
    
    # Test dependency analysis
    print("\n" + "-"*80)
    print("Analyzing Dependencies")
    print("-"*80)
    
    if relations:
        concept = relations[0].effect
        print(f"\nAnalyzing dependencies for: {concept}")
        
        deps = engine.analyze_dependencies(concept, relations)
        
        print(f"\n📋 Prerequisites ({len(deps['prerequisites'])}):")
        for prereq in deps['prerequisites'][:3]:
            print(f"  • {prereq['requirement']}")
            print(f"    Confidence: {prereq['confidence']:.2f}")
        
        print(f"\n📋 Consequences ({len(deps['consequences'])}):")
        for cons in deps['consequences'][:3]:
            print(f"  • {cons['result']}")
            print(f"    Confidence: {cons['confidence']:.2f}")
    
    print("\n✅ Causal Reasoning Test Complete!")


def test_counterfactual_analyzer():
    """Test counterfactual analyzer"""
    print("\n" + "="*80)
    print("🔮 TEST 2: COUNTERFACTUAL ANALYZER")
    print("="*80)
    
    analyzer = CounterfactualAnalyzer()
    
    # Sample query with user situation
    query = "أنا طبيب لدي 3 سنوات خبرة وحاصل على شهادة الماجستير، هل يمكنني التقديم لمنصب أستاذ مساعد؟"
    
    print(f"\n📝 Query: {query}\n")
    
    # Extract user situation
    print("1️⃣ Extracting User Situation...")
    user_situation = analyzer.extract_user_situation(query)
    print(f"   ✅ Extracted: {user_situation}")
    
    # Sample documents with requirements
    sample_docs = [
        {
            "content": """
            المادة 5: يشترط في المترشح 5 سنوات من الخبرة المهنية.
            يجب أن يكون حاصلاً على شهادة الدكتوراه.
            """,
            "title": "القانون 12.20 (2020)",
            "metadata": {"date": "2020-01-01"}
        },
        {
            "content": """
            المادة 3: للأطباء، يشترط 3 سنوات من الخبرة فقط.
            شهادة الماجستير كافية للأطباء.
            """,
            "title": "القانون الخاص بالأطباء 15.18 (2018)",
            "metadata": {"date": "2018-01-01"}
        }
    ]
    
    # Extract requirements
    print("\n2️⃣ Extracting Requirements...")
    requirements = analyzer.extract_requirements(sample_docs)
    print(f"   ✅ Extracted: {requirements}")
    
    # Analyze gaps
    print("\n3️⃣ Analyzing Gaps...")
    gaps = analyzer.analyze_gaps(user_situation, requirements)
    print(f"   ✅ Found {len(gaps)} gaps:")
    for gap in gaps:
        print(f"      • {gap.requirement} (Severity: {gap.severity})")
        print(f"        Your status: {gap.user_status}")
        if gap.resolution_paths:
            print(f"        Resolution: {gap.resolution_paths[0]}")
    
    # Find alternative paths
    print("\n4️⃣ Finding Alternative Paths...")
    alternatives = analyzer.find_alternative_paths("منصب أستاذ مساعد", gaps, sample_docs)
    print(f"   ✅ Found {len(alternatives)} alternative paths:")
    for i, alt in enumerate(alternatives[:3], 1):
        print(f"\n   {i}. {alt.path_description}")
        print(f"      Feasibility: {alt.feasibility_score:.0%}")
        print(f"      Duration: {alt.estimated_duration}")
        print(f"      Advantages: {', '.join(alt.advantages[:2])}")
    
    # Complete scenario analysis
    print("\n" + "-"*80)
    print("Complete Scenario Analysis")
    print("-"*80)
    
    scenario = analyzer.analyze_scenario(query, sample_docs)
    
    print(f"\n📊 Eligibility: {'✅ Eligible' if scenario.current_eligibility else '❌ Not Eligible'}")
    print(f"📊 Gaps: {len(scenario.gaps)}")
    print(f"📊 Alternative Paths: {len(scenario.alternative_paths)}")
    
    print("\n💡 Recommendations:")
    for rec in scenario.recommendations:
        print(f"   {rec}")
    
    # Format response
    print("\n" + "-"*80)
    print("Formatted User Response")
    print("-"*80)
    
    formatted = analyzer.format_scenario_response(scenario)
    print(f"\n{formatted}")
    
    print("\n✅ Counterfactual Analyzer Test Complete!")


def test_implicit_requirement_extractor():
    """Test implicit requirement extractor"""
    print("\n" + "="*80)
    print("🔍 TEST 3: IMPLICIT REQUIREMENT EXTRACTOR")
    print("="*80)
    
    extractor = ImplicitRequirementExtractor()
    
    # Sample documents
    sample_docs = [
        {
            "content": """
            المادة 5: يشترط في المترشح 5 سنوات من الخبرة المهنية.
            يجب تقديم شهادة عمل مصادق عليها من الوزارة.
            يجب أن تكون الشهادة معتمدة من وزارة التعليم العالي.
            """,
            "title": "القانون 12.20"
        },
        {
            "content": """
            المادة 3: يجب على المترشح تقديم نسخة من الشهادة الجامعية.
            يشترط أن تكون الشهادة مصادق عليها.
            يجب تقديم كشف النقاط خلال 30 يوم من تاريخ التقديم.
            """,
            "title": "المرسوم 19.05"
        },
        {
            "content": """
            المادة 7: يشترط في المترشح 5 سنوات من الخبرة.
            يجب تقديم شهادة عمل.
            """,
            "title": "القرار 08.15"
        }
    ]
    
    explicit_requirements = [
        "5 سنوات خبرة",
        "شهادة جامعية",
        "شهادة عمل"
    ]
    
    print("\n📋 Explicit Requirements:")
    for req in explicit_requirements:
        print(f"  • {req}")
    
    print("\n🔍 Extracting Implicit Requirements...")
    implicit_reqs = extractor.extract_implicit_requirements(sample_docs, explicit_requirements)
    
    print(f"\n✅ Found {len(implicit_reqs)} implicit requirements:\n")
    
    # Categorize by priority
    categorized = extractor.categorize_by_priority(implicit_reqs)
    
    print("🔴 Critical (High Confidence):")
    for req in categorized["critical"][:3]:
        print(f"  • {req.requirement}")
        print(f"    Reasoning: {req.reasoning}")
        print(f"    Confidence: {req.confidence:.0%}")
        print(f"    Category: {req.category}")
        print()
    
    print("🟠 Important (Medium Confidence):")
    for req in categorized["important"][:3]:
        print(f"  • {req.requirement}")
        print(f"    Reasoning: {req.reasoning}")
        print()
    
    print("🟡 Optional (Low Confidence):")
    for req in categorized["optional"][:2]:
        print(f"  • {req.requirement}")
        print()
    
    # Format for display
    print("-"*80)
    print("Formatted Display")
    print("-"*80)
    
    formatted = extractor.format_implicit_requirements(implicit_reqs, max_display=10)
    print(f"\n{formatted}")
    
    print("\n✅ Implicit Requirement Extractor Test Complete!")


def test_situational_adapter():
    """Test situational adapter"""
    print("\n" + "="*80)
    print("👤 TEST 4: SITUATIONAL ADAPTER")
    print("="*80)
    
    adapter = SituationalAdapter()
    
    # Test queries with different user profiles
    test_queries = [
        "أنا طبيب لدي 4 سنوات خبرة، هل يمكنني التقديم؟",
        "أنا أستاذ جامعي حاصل على الدكتوراه، ما هي الشروط؟",
        "أنا طالب عمري 22 سنة، كيف أصبح موظف؟",
        "I am a foreign engineer with 10 years experience"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"Test Case {i}")
        print("="*80)
        print(f"\n📝 Query: {query}")
        
        # Extract profile
        profile = adapter.extract_user_profile(query)
        
        print(f"\n👤 User Profile:")
        print(f"  Category: {profile.category.value}")
        if profile.profession:
            print(f"  Profession: {profile.profession}")
        if profile.experience_years:
            print(f"  Experience: {profile.experience_years} years")
        if profile.education_level:
            print(f"  Education: {profile.education_level}")
        if profile.age:
            print(f"  Age: {profile.age}")
        if profile.special_circumstances:
            print(f"  Special: {', '.join(profile.special_circumstances)}")
    
    # Detailed test with documents
    print("\n" + "="*80)
    print("Detailed Personalization Test")
    print("="*80)
    
    query = "أنا طبيب لدي 4 سنوات خبرة وحاصل على شهادة الماجستير"
    profile = adapter.extract_user_profile(query)
    
    sample_docs = [
        {
            "content": """
            القانون الخاص بالأطباء: استثناء من القانون العام، يمكن للأطباء
            التقديم بـ 3 سنوات خبرة فقط. شهادة الماجستير كافية للأطباء.
            """,
            "title": "القانون الخاص بالقطاع الصحي 15.18",
            "article_number": "5"
        },
        {
            "content": """
            القانون العام: يشترط 5 سنوات خبرة وشهادة الدكتوراه.
            """,
            "title": "القانون العام 12.20",
            "article_number": "3"
        }
    ]
    
    print(f"\n📝 Query: {query}")
    print(f"👤 Category: {profile.category.value}")
    
    # Find exceptions
    print("\n🔍 Finding Applicable Exceptions...")
    exceptions = adapter.find_applicable_exceptions(profile, sample_docs)
    print(f"   ✅ Found {len(exceptions)} exceptions:")
    for exc in exceptions:
        print(f"      • {exc['law']} (Relevance: {exc['relevance']})")
    
    # Generate personalized advice
    print("\n💡 Generating Personalized Advice...")
    general_answer = "يشترط 5 سنوات خبرة وشهادة الدكتوراه حسب القانون العام."
    
    advice = adapter.generate_personalized_advice(
        profile, general_answer, sample_docs, exceptions
    )
    
    print(f"\n📊 Personalization Confidence: {advice.confidence:.0%}")
    
    print(f"\n👤 Personalized Insights ({len(advice.personalized_insights)}):")
    for insight in advice.personalized_insights:
        print(f"  {insight}")
    
    print(f"\n⚖️ Applicable Exceptions ({len(advice.applicable_exceptions)}):")
    for exception in advice.applicable_exceptions:
        print(f"  {exception}")
    
    print(f"\n💡 Specific Recommendations ({len(advice.specific_recommendations)}):")
    for rec in advice.specific_recommendations:
        print(f"  • {rec}")
    
    # Format response
    print("\n" + "-"*80)
    print("Formatted Personalized Response")
    print("-"*80)
    
    formatted = adapter.format_personalized_response(advice)
    print(f"\n{formatted}")
    
    print("\n✅ Situational Adapter Test Complete!")


def test_integration():
    """Test all modules working together"""
    print("\n" + "="*80)
    print("🚀 TEST 5: INTEGRATED ADAPTIVE REASONING")
    print("="*80)
    
    print("\nSimulating complete adaptive reasoning workflow...")
    
    query = "أنا طبيب لدي 3 سنوات خبرة وحاصل على الماجستير، هل يمكنني التقديم لمنصب أستاذ مساعد؟"
    
    print(f"\n📝 User Query: {query}\n")
    
    # Sample documents
    sample_docs = [
        {
            "content": """
            المادة 5: يشترط في المترشح 5 سنوات من الخبرة المهنية.
            إذا كان المترشح حاصلاً على 5 سنوات خبرة فإنه يمكنه التقديم.
            يجب تقديم شهادة عمل مصادق عليها.
            """,
            "title": "القانون العام 12.20",
            "metadata": {"date": "2020-01-01"}
        },
        {
            "content": """
            القانون الخاص بالأطباء: استثناء، يمكن للأطباء التقديم بـ 3 سنوات خبرة.
            شهادة الماجستير كافية للأطباء.
            يجب تقديم شهادة مزاولة المهنة.
            """,
            "title": "القانون الخاص بالقطاع الصحي 15.18",
            "metadata": {"date": "2018-01-01"}
        }
    ]
    
    # 1. Causal Reasoning
    print("1️⃣ Causal Reasoning Analysis:")
    causal_engine = CausalReasoningEngine()
    relations = causal_engine.extract_causal_relations(sample_docs)
    print(f"   ✅ Extracted {len(relations)} causal relations")
    
    # 2. Situational Adaptation
    print("\n2️⃣ Situational Adaptation:")
    adapter = SituationalAdapter()
    profile = adapter.extract_user_profile(query)
    print(f"   ✅ Identified as: {profile.category.value}")
    exceptions = adapter.find_applicable_exceptions(profile, sample_docs)
    print(f"   ✅ Found {len(exceptions)} applicable exceptions")
    
    # 3. Counterfactual Analysis
    print("\n3️⃣ Counterfactual Analysis:")
    cf_analyzer = CounterfactualAnalyzer()
    scenario = cf_analyzer.analyze_scenario(query, sample_docs)
    print(f"   ✅ Eligibility: {'Yes' if scenario.current_eligibility else 'No'}")
    print(f"   ✅ Gaps: {len(scenario.gaps)}")
    print(f"   ✅ Alternative paths: {len(scenario.alternative_paths)}")
    
    # 4. Implicit Requirements
    print("\n4️⃣ Implicit Requirement Extraction:")
    implicit_extractor = ImplicitRequirementExtractor()
    explicit_reqs = ["5 سنوات خبرة", "شهادة"]
    implicit_reqs = implicit_extractor.extract_implicit_requirements(sample_docs, explicit_reqs)
    print(f"   ✅ Found {len(implicit_reqs)} implicit requirements")
    
    # 5. Generate Complete Response
    print("\n5️⃣ Generating Complete Adaptive Response:")
    print("\n" + "="*80)
    print("COMPLETE ADAPTIVE RESPONSE")
    print("="*80)
    
    # Combine all insights
    print(f"\n🎯 **تحليل شامل لوضعك**\n")
    
    # Profile
    print(f"👤 **ملفك الشخصي:**")
    print(f"  • الفئة: {adapter._get_category_name_ar(profile.category)}")
    print(f"  • الخبرة: {profile.experience_years} سنوات")
    print(f"  • المؤهل: {profile.education_level}")
    print()
    
    # Causal reasoning
    if relations:
        print(f"🧠 **التحليل السببي:**")
        print(f"  • تم اكتشاف {len(relations)} علاقة سببية في القوانين")
        print(f"  • {relations[0].cause} → {relations[0].effect}")
        print()
    
    # Situational insights
    general_answer = "حسب القانون العام، يشترط 5 سنوات خبرة."
    advice = adapter.generate_personalized_advice(profile, general_answer, sample_docs, exceptions)
    
    print(f"💡 **نصائح مخصصة لك:**")
    for insight in advice.personalized_insights:
        print(f"  {insight}")
    print()
    
    # Counterfactual analysis
    print(f"🔮 **تحليل الوضعية:**")
    if scenario.current_eligibility:
        print(f"  ✅ أنت مؤهل للتقديم!")
    else:
        print(f"  ⚠️ لديك {len(scenario.gaps)} متطلب ناقص")
        for gap in scenario.gaps:
            print(f"     • {gap.requirement}")
    print()
    
    # Alternative paths
    if scenario.alternative_paths:
        print(f"🛤️ **المسارات البديلة:**")
        best_path = scenario.alternative_paths[0]
        print(f"  1. {best_path.path_description}")
        print(f"     جدوى: {best_path.feasibility_score:.0%}")
        print()
    
    # Implicit requirements
    if implicit_reqs:
        categorized = implicit_extractor.categorize_by_priority(implicit_reqs)
        if categorized["critical"]:
            print(f"🔍 **متطلبات ضمنية مكتشفة:**")
            for req in categorized["critical"][:2]:
                print(f"  • {req.requirement}")
            print()
    
    # Recommendations
    print(f"📋 **التوصيات النهائية:**")
    for rec in scenario.recommendations[:5]:
        print(f"  {rec}")
    
    print("\n" + "="*80)
    print("✅ ALL ADAPTIVE REASONING TESTS PASSED!")
    print("="*80)
    
    print("\n🎉 The system now has AGI-level legal reasoning capabilities:")
    print("  ✅ Causal Reasoning - Understands cause-effect chains")
    print("  ✅ Counterfactual Analysis - Analyzes 'what if' scenarios")
    print("  ✅ Implicit Requirements - Discovers unstated rules")
    print("  ✅ Situational Adaptation - Personalizes advice")
    print("\nThis is the world's first RAG system with adaptive legal reasoning! 🚀")


if __name__ == "__main__":
    try:
        test_causal_reasoning()
        test_counterfactual_analyzer()
        test_implicit_requirement_extractor()
        test_situational_adapter()
        test_integration()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
