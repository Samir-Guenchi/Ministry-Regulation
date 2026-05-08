"""
Counterfactual Analyzer for Legal Scenarios
Analyzes "what if" scenarios and alternative paths
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class GapType(Enum):
    """Types of gaps in requirements"""
    MISSING_QUALIFICATION = "missing_qualification"
    INSUFFICIENT_EXPERIENCE = "insufficient_experience"
    MISSING_DOCUMENT = "missing_document"
    AGE_REQUIREMENT = "age_requirement"
    OTHER = "other"


@dataclass
class RequirementGap:
    """Represents a gap between user situation and requirements"""
    requirement: str
    user_status: str
    gap_type: GapType
    severity: str  # "critical", "major", "minor"
    can_be_resolved: bool
    resolution_paths: List[str]
    estimated_time: Optional[str] = None


@dataclass
class AlternativePath:
    """Represents an alternative path to achieve a goal"""
    path_description: str
    requirements: List[str]
    advantages: List[str]
    disadvantages: List[str]
    feasibility_score: float
    estimated_duration: Optional[str] = None


@dataclass
class CounterfactualScenario:
    """Represents a what-if scenario analysis"""
    original_query: str
    user_situation: Dict
    target_goal: str
    current_eligibility: bool
    gaps: List[RequirementGap]
    alternative_paths: List[AlternativePath]
    recommendations: List[str]


class CounterfactualAnalyzer:
    """
    Analyzes counterfactual scenarios for legal queries
    - Gap analysis between user situation and requirements
    - Alternative path discovery
    - "What if" scenario evaluation
    """
    
    def __init__(self):
        # Patterns for extracting user situation
        self.situation_patterns = {
            "experience_years": [
                r"(?:لدي|عندي|أملك)\s+(\d+)\s+(?:سنوات?|سنة)\s+(?:من\s+)?(?:الخبرة|خبرة)",
                r"(?:I have|with)\s+(\d+)\s+years?\s+(?:of\s+)?experience",
                r"(?:j'ai|avec)\s+(\d+)\s+ans?\s+d'expérience"
            ],
            "degree": [
                r"(?:لدي|عندي|حاصل على)\s+(?:شهادة|دبلوم)\s+(\w+(?:\s+\w+){0,3})",
                r"(?:I have|with)\s+(?:a\s+)?(\w+)\s+degree",
                r"(?:j'ai|avec)\s+(?:un\s+)?(?:diplôme|licence)\s+(?:de\s+)?(\w+)"
            ],
            "age": [
                r"(?:عمري|سني)\s+(\d+)\s+(?:سنة|عام)",
                r"(?:I am|I'm)\s+(\d+)\s+years?\s+old",
                r"(?:j'ai)\s+(\d+)\s+ans"
            ],
            "position": [
                r"(?:أنا|أعمل)\s+(\w+(?:\s+\w+){0,3})",
                r"(?:I am|I work as)\s+(?:a\s+)?(\w+(?:\s+\w+){0,3})",
                r"(?:je suis|je travaille comme)\s+(\w+(?:\s+\w+){0,3})"
            ]
        }
        
        # Requirement extraction patterns
        self.requirement_patterns = {
            "experience_years": [
                r"(?:يشترط|يتطلب|يجب)\s+(\d+)\s+(?:سنوات?|سنة)\s+(?:من\s+)?(?:الخبرة|خبرة)",
                r"requires?\s+(\d+)\s+years?\s+(?:of\s+)?experience",
                r"(?:exige|requiert)\s+(\d+)\s+ans?\s+d'expérience"
            ],
            "degree": [
                r"(?:يشترط|يتطلب)\s+(?:شهادة|دبلوم)\s+(\w+(?:\s+\w+){0,3})",
                r"requires?\s+(?:a\s+)?(\w+)\s+degree",
                r"(?:exige|requiert)\s+(?:un\s+)?(?:diplôme|licence)\s+(?:de\s+)?(\w+)"
            ],
            "age": [
                r"(?:يشترط|يجب)\s+(?:أن يكون|العمر)\s+(\d+)\s+(?:سنة|عام)",
                r"(?:must be|requires?)\s+(\d+)\s+years?\s+old",
                r"(?:doit avoir|exige)\s+(\d+)\s+ans"
            ]
        }
    
    def extract_user_situation(self, query: str) -> Dict:
        """Extract user's current situation from query"""
        situation = {}
        
        for key, patterns in self.situation_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    situation[key] = match.group(1).strip()
                    break
        
        logger.info(f"Extracted user situation: {situation}")
        return situation
    
    def extract_requirements(self, documents: List[Dict]) -> Dict:
        """Extract requirements from documents"""
        requirements = {}
        
        for doc in documents:
            content = doc.get("content", "")
            
            for key, patterns in self.requirement_patterns.items():
                if key not in requirements:
                    for pattern in patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            requirements[key] = {
                                "value": match.group(1).strip(),
                                "source": doc.get("title", "Unknown"),
                                "article": doc.get("article_number")
                            }
                            break
        
        logger.info(f"Extracted requirements: {requirements}")
        return requirements
    
    def analyze_gaps(
        self,
        user_situation: Dict,
        requirements: Dict
    ) -> List[RequirementGap]:
        """Analyze gaps between user situation and requirements"""
        gaps = []
        
        # Check experience years
        if "experience_years" in requirements:
            req_years = int(requirements["experience_years"]["value"])
            user_years = int(user_situation.get("experience_years", 0))
            
            if user_years < req_years:
                gap = RequirementGap(
                    requirement=f"{req_years} سنوات خبرة",
                    user_status=f"{user_years} سنوات",
                    gap_type=GapType.INSUFFICIENT_EXPERIENCE,
                    severity="critical" if (req_years - user_years) > 2 else "major",
                    can_be_resolved=True,
                    resolution_paths=[
                        f"انتظر {req_years - user_years} سنوات إضافية",
                        "تحقق من إمكانية احتساب فترات التدريب",
                        "ابحث عن مناصب بمتطلبات أقل"
                    ],
                    estimated_time=f"{req_years - user_years} سنوات"
                )
                gaps.append(gap)
        
        # Check degree
        if "degree" in requirements and "degree" in user_situation:
            req_degree = requirements["degree"]["value"].lower()
            user_degree = user_situation["degree"].lower()
            
            # Simple degree hierarchy
            degree_levels = {
                "دكتوراه": 4, "doctorate": 4, "phd": 4,
                "ماجستير": 3, "master": 3,
                "ليسانس": 2, "bachelor": 2, "licence": 2,
                "بكالوريا": 1, "high school": 1, "baccalauréat": 1
            }
            
            req_level = degree_levels.get(req_degree, 0)
            user_level = degree_levels.get(user_degree, 0)
            
            if user_level < req_level:
                gap = RequirementGap(
                    requirement=f"شهادة {requirements['degree']['value']}",
                    user_status=f"شهادة {user_situation['degree']}",
                    gap_type=GapType.MISSING_QUALIFICATION,
                    severity="critical",
                    can_be_resolved=True,
                    resolution_paths=[
                        "التسجيل في برنامج دراسات عليا",
                        "البحث عن معادلة للشهادة",
                        "البحث عن مناصب بمتطلبات أقل"
                    ],
                    estimated_time="2-5 سنوات حسب البرنامج"
                )
                gaps.append(gap)
        
        # Check age
        if "age" in requirements and "age" in user_situation:
            req_age = int(requirements["age"]["value"])
            user_age = int(user_situation["age"])
            
            if user_age < req_age:
                gap = RequirementGap(
                    requirement=f"{req_age} سنة على الأقل",
                    user_status=f"{user_age} سنة",
                    gap_type=GapType.AGE_REQUIREMENT,
                    severity="minor",
                    can_be_resolved=True,
                    resolution_paths=[
                        f"انتظر {req_age - user_age} سنة"
                    ],
                    estimated_time=f"{req_age - user_age} سنة"
                )
                gaps.append(gap)
        
        return gaps
    
    def find_alternative_paths(
        self,
        target_goal: str,
        current_gaps: List[RequirementGap],
        documents: List[Dict]
    ) -> List[AlternativePath]:
        """Find alternative paths to achieve the goal"""
        alternatives = []
        
        # Path 1: Wait and fulfill requirements
        if current_gaps:
            wait_time = max(
                (gap.estimated_time for gap in current_gaps if gap.estimated_time),
                default="غير محدد"
            )
            
            alternatives.append(AlternativePath(
                path_description="انتظر واستكمل المتطلبات الناقصة",
                requirements=[gap.requirement for gap in current_gaps],
                advantages=[
                    "تحقيق الهدف الأصلي",
                    "استيفاء جميع الشروط القانونية"
                ],
                disadvantages=[
                    f"يتطلب وقتاً: {wait_time}",
                    "قد تتغير المتطلبات"
                ],
                feasibility_score=0.7,
                estimated_duration=wait_time
            ))
        
        # Path 2: Look for junior/alternative positions
        alternatives.append(AlternativePath(
            path_description="ابحث عن مناصب بديلة بمتطلبات أقل",
            requirements=["البحث في القوانين عن مناصب مشابهة"],
            advantages=[
                "بداية فورية",
                "اكتساب خبرة",
                "إمكانية الترقية لاحقاً"
            ],
            disadvantages=[
                "منصب أقل",
                "راتب أقل محتمل"
            ],
            feasibility_score=0.8,
            estimated_duration="فوري"
        ))
        
        # Path 3: Check for special categories
        alternatives.append(AlternativePath(
            path_description="تحقق من الفئات الخاصة أو الاستثناءات",
            requirements=["مراجعة القوانين الخاصة بفئتك المهنية"],
            advantages=[
                "قد تكون المتطلبات أقل",
                "مسارات مخصصة"
            ],
            disadvantages=[
                "قد لا تنطبق عليك",
                "إجراءات إضافية"
            ],
            feasibility_score=0.5,
            estimated_duration="يعتمد على الفئة"
        ))
        
        # Path 4: Training/internship path
        if any(gap.gap_type == GapType.INSUFFICIENT_EXPERIENCE for gap in current_gaps):
            alternatives.append(AlternativePath(
                path_description="التسجيل في برامج تدريب أو تكوين",
                requirements=["البحث عن برامج تدريب معتمدة"],
                advantages=[
                    "احتساب فترة التدريب كخبرة",
                    "تطوير المهارات"
                ],
                disadvantages=[
                    "قد يتطلب رسوم",
                    "وقت إضافي"
                ],
                feasibility_score=0.6,
                estimated_duration="6 أشهر - 2 سنة"
            ))
        
        # Sort by feasibility
        alternatives.sort(key=lambda x: x.feasibility_score, reverse=True)
        
        return alternatives
    
    def generate_recommendations(
        self,
        gaps: List[RequirementGap],
        alternatives: List[AlternativePath]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Immediate actions
        if not gaps:
            recommendations.append("✅ أنت مؤهل! يمكنك التقديم مباشرة.")
        else:
            recommendations.append(f"⚠️ لديك {len(gaps)} متطلب ناقص يجب استكماله.")
        
        # Priority actions
        critical_gaps = [g for g in gaps if g.severity == "critical"]
        if critical_gaps:
            recommendations.append(
                f"🔴 أولوية عالية: استكمل {len(critical_gaps)} متطلب حرج"
            )
            for gap in critical_gaps[:2]:
                recommendations.append(f"   • {gap.requirement}")
        
        # Best alternative path
        if alternatives:
            best_path = alternatives[0]
            recommendations.append(
                f"💡 المسار الأفضل: {best_path.path_description} "
                f"(جدوى: {best_path.feasibility_score:.0%})"
            )
        
        # Timeline
        total_time = self._estimate_total_time(gaps)
        if total_time:
            recommendations.append(f"⏱️ الوقت المقدر: {total_time}")
        
        # Next steps
        recommendations.append("📋 الخطوات التالية:")
        if gaps:
            for i, gap in enumerate(gaps[:3], 1):
                if gap.resolution_paths:
                    recommendations.append(f"   {i}. {gap.resolution_paths[0]}")
        
        return recommendations
    
    def analyze_scenario(
        self,
        query: str,
        documents: List[Dict],
        target_goal: Optional[str] = None
    ) -> CounterfactualScenario:
        """Perform complete counterfactual analysis"""
        
        # Extract user situation
        user_situation = self.extract_user_situation(query)
        
        # Extract requirements
        requirements = self.extract_requirements(documents)
        
        # Analyze gaps
        gaps = self.analyze_gaps(user_situation, requirements)
        
        # Determine eligibility
        current_eligibility = len(gaps) == 0
        
        # Find alternative paths
        if not target_goal:
            target_goal = "الالتحاق بالمنصب المطلوب"
        
        alternatives = self.find_alternative_paths(target_goal, gaps, documents)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(gaps, alternatives)
        
        scenario = CounterfactualScenario(
            original_query=query,
            user_situation=user_situation,
            target_goal=target_goal,
            current_eligibility=current_eligibility,
            gaps=gaps,
            alternative_paths=alternatives,
            recommendations=recommendations
        )
        
        logger.info(
            f"Counterfactual analysis: Eligibility={current_eligibility}, "
            f"Gaps={len(gaps)}, Alternatives={len(alternatives)}"
        )
        
        return scenario
    
    def _estimate_total_time(self, gaps: List[RequirementGap]) -> Optional[str]:
        """Estimate total time to resolve all gaps"""
        if not gaps:
            return None
        
        # Extract years from time estimates
        total_years = 0
        for gap in gaps:
            if gap.estimated_time:
                match = re.search(r'(\d+)\s+(?:سنوات?|سنة)', gap.estimated_time)
                if match:
                    total_years += int(match.group(1))
        
        if total_years > 0:
            return f"{total_years} سنوات تقريباً"
        
        return "يعتمد على الظروف"
    
    def format_scenario_response(self, scenario: CounterfactualScenario) -> str:
        """Format scenario analysis as user-friendly response"""
        lines = []
        
        lines.append("🔍 **تحليل الوضعية**\n")
        
        # User situation
        if scenario.user_situation:
            lines.append("📊 **وضعك الحالي:**")
            for key, value in scenario.user_situation.items():
                label = {
                    "experience_years": "الخبرة",
                    "degree": "الشهادة",
                    "age": "العمر",
                    "position": "المنصب"
                }.get(key, key)
                lines.append(f"  • {label}: {value}")
            lines.append("")
        
        # Eligibility
        if scenario.current_eligibility:
            lines.append("✅ **أنت مؤهل للتقديم!**\n")
        else:
            lines.append(f"⚠️ **المتطلبات الناقصة: {len(scenario.gaps)}**\n")
            
            for i, gap in enumerate(scenario.gaps, 1):
                severity_emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(gap.severity, "⚪")
                lines.append(f"{severity_emoji} **{i}. {gap.requirement}**")
                lines.append(f"   وضعك: {gap.user_status}")
                if gap.estimated_time:
                    lines.append(f"   الوقت المطلوب: {gap.estimated_time}")
                lines.append("")
        
        # Alternative paths
        if scenario.alternative_paths:
            lines.append("🛤️ **المسارات البديلة:**\n")
            for i, path in enumerate(scenario.alternative_paths[:3], 1):
                lines.append(f"**{i}. {path.path_description}**")
                lines.append(f"   جدوى: {path.feasibility_score:.0%} | مدة: {path.estimated_duration}")
                lines.append(f"   ✅ مزايا: {', '.join(path.advantages[:2])}")
                lines.append(f"   ❌ عيوب: {', '.join(path.disadvantages[:2])}")
                lines.append("")
        
        # Recommendations
        if scenario.recommendations:
            lines.append("💡 **التوصيات:**\n")
            for rec in scenario.recommendations:
                lines.append(rec)
        
        return "\n".join(lines)
