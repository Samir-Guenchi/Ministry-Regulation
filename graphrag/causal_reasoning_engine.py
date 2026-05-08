"""
Causal Reasoning Engine for Legal Documents
Builds cause-effect chains and logical dependencies between laws
"""
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CausalRelationType(Enum):
    """Types of causal relationships"""
    REQUIRES = "requires"  # A requires B
    IMPLIES = "implies"  # A implies B
    ENABLES = "enables"  # A enables B
    PREVENTS = "prevents"  # A prevents B
    CONDITIONAL = "conditional"  # If A then B


@dataclass
class CausalRelation:
    """Represents a causal relationship between legal concepts"""
    cause: str
    effect: str
    relation_type: CausalRelationType
    confidence: float
    source_law: str
    source_article: Optional[str] = None
    conditions: List[str] = None
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []


@dataclass
class CausalChain:
    """Represents a chain of causal relationships"""
    chain: List[CausalRelation]
    start_concept: str
    end_concept: str
    total_confidence: float
    reasoning_path: str


class CausalReasoningEngine:
    """
    Builds and analyzes causal relationships in legal documents
    - Extracts cause-effect patterns
    - Builds reasoning chains
    - Infers logical dependencies
    """
    
    def __init__(self):
        # Causal patterns in Arabic
        self.causal_patterns = {
            CausalRelationType.REQUIRES: [
                r"يشترط\s+(.+?)\s+(?:أن|في|على)\s+(.+?)(?:\.|،|$)",
                r"يتطلب\s+(.+?)\s+(?:أن|في|على)\s+(.+?)(?:\.|،|$)",
                r"يجب\s+(?:أن|على)\s+(.+?)\s+(?:أن|في)\s+(.+?)(?:\.|،|$)",
                r"requires?\s+(.+?)\s+to\s+(.+?)(?:\.|,|$)",
                r"(?:exige|requiert)\s+(.+?)\s+(?:de|à)\s+(.+?)(?:\.|,|$)"
            ],
            CausalRelationType.IMPLIES: [
                r"إذا\s+(.+?)\s+(?:ف|فإن|فإنه)\s+(.+?)(?:\.|،|$)",
                r"في حالة\s+(.+?)\s+(?:ف|يتم|يجب)\s+(.+?)(?:\.|،|$)",
                r"عند\s+(.+?)\s+(?:ف|يتم|يجب)\s+(.+?)(?:\.|،|$)",
                r"if\s+(.+?)\s+then\s+(.+?)(?:\.|,|$)",
                r"si\s+(.+?)\s+alors\s+(.+?)(?:\.|,|$)"
            ],
            CausalRelationType.ENABLES: [
                r"يمكن\s+(?:ل)?(.+?)\s+(?:أن|من)\s+(.+?)(?:\.|،|$)",
                r"يسمح\s+(?:ل)?(.+?)\s+(?:ب|أن)\s+(.+?)(?:\.|،|$)",
                r"(?:allows?|enables?)\s+(.+?)\s+to\s+(.+?)(?:\.|,|$)",
                r"permet\s+(?:à|de)\s+(.+?)\s+de\s+(.+?)(?:\.|,|$)"
            ],
            CausalRelationType.PREVENTS: [
                r"يمنع\s+(.+?)\s+(?:من|عن)\s+(.+?)(?:\.|،|$)",
                r"لا يجوز\s+(?:ل)?(.+?)\s+(?:أن)\s+(.+?)(?:\.|،|$)",
                r"prevents?\s+(.+?)\s+from\s+(.+?)(?:\.|,|$)",
                r"empêche\s+(.+?)\s+de\s+(.+?)(?:\.|,|$)"
            ],
            CausalRelationType.CONDITIONAL: [
                r"بشرط\s+(.+?)\s+(?:ف|يتم|يمكن)\s+(.+?)(?:\.|،|$)",
                r"على أن\s+(.+?)\s+(?:ف|يتم|يمكن)\s+(.+?)(?:\.|،|$)",
                r"provided\s+(?:that\s+)?(.+?)\s+then\s+(.+?)(?:\.|,|$)",
                r"à condition\s+(?:que\s+)?(.+?)\s+alors\s+(.+?)(?:\.|,|$)"
            ]
        }
        
        # Concept extraction patterns
        self.concept_patterns = [
            r"(?:رتبة|منصب|وظيفة)\s+(\w+(?:\s+\w+){0,3})",  # Position/rank
            r"(?:شهادة|دبلوم)\s+(\w+(?:\s+\w+){0,3})",  # Degree
            r"(\d+)\s+(?:سنوات?|سنة)\s+(?:من\s+)?(?:الخبرة|خبرة)",  # Years experience
            r"(?:تصريح|ترخيص|إذن)\s+(\w+(?:\s+\w+){0,3})",  # Permission/license
        ]
    
    def extract_causal_relations(self, documents: List[Dict]) -> List[CausalRelation]:
        """Extract causal relationships from documents"""
        relations = []
        
        for doc in documents:
            content = doc.get("content", "")
            law_name = doc.get("title", "Unknown")
            
            # Extract relations for each type
            for relation_type, patterns in self.causal_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    
                    for match in matches:
                        if len(match.groups()) >= 2:
                            cause = match.group(1).strip()
                            effect = match.group(2).strip()
                            
                            # Clean up extracted text
                            cause = self._clean_concept(cause)
                            effect = self._clean_concept(effect)
                            
                            if cause and effect and len(cause) < 200 and len(effect) < 200:
                                relation = CausalRelation(
                                    cause=cause,
                                    effect=effect,
                                    relation_type=relation_type,
                                    confidence=0.8,
                                    source_law=law_name,
                                    source_article=doc.get("article_number")
                                )
                                relations.append(relation)
                                
                                logger.debug(
                                    f"Extracted {relation_type.value}: "
                                    f"{cause} → {effect} from {law_name}"
                                )
        
        logger.info(f"Extracted {len(relations)} causal relations from {len(documents)} documents")
        
        return relations
    
    def build_causal_chain(
        self,
        start_concept: str,
        end_concept: str,
        relations: List[CausalRelation],
        max_depth: int = 5
    ) -> Optional[CausalChain]:
        """Build a causal chain from start to end concept"""
        
        # BFS to find shortest path
        queue = [(start_concept, [], 1.0)]
        visited = set()
        
        while queue:
            current, path, confidence = queue.pop(0)
            
            if current in visited:
                continue
            
            visited.add(current)
            
            # Check if we reached the end
            if self._concepts_match(current, end_concept):
                if path:
                    reasoning = self._build_reasoning_path(path)
                    return CausalChain(
                        chain=path,
                        start_concept=start_concept,
                        end_concept=end_concept,
                        total_confidence=confidence,
                        reasoning_path=reasoning
                    )
            
            # Don't go too deep
            if len(path) >= max_depth:
                continue
            
            # Find next relations
            for relation in relations:
                if self._concepts_match(relation.cause, current):
                    new_path = path + [relation]
                    new_confidence = confidence * relation.confidence
                    queue.append((relation.effect, new_path, new_confidence))
        
        return None
    
    def find_all_effects(
        self,
        concept: str,
        relations: List[CausalRelation],
        max_depth: int = 3
    ) -> List[Tuple[str, List[CausalRelation]]]:
        """Find all effects that can result from a concept"""
        effects = []
        queue = [(concept, [], 1.0, 0)]
        visited = set()
        
        while queue:
            current, path, confidence, depth = queue.pop(0)
            
            if current in visited or depth >= max_depth:
                continue
            
            visited.add(current)
            
            # Find direct effects
            for relation in relations:
                if self._concepts_match(relation.cause, current):
                    new_path = path + [relation]
                    effects.append((relation.effect, new_path))
                    
                    # Continue searching
                    queue.append((
                        relation.effect,
                        new_path,
                        confidence * relation.confidence,
                        depth + 1
                    ))
        
        return effects
    
    def find_all_causes(
        self,
        concept: str,
        relations: List[CausalRelation],
        max_depth: int = 3
    ) -> List[Tuple[str, List[CausalRelation]]]:
        """Find all causes that can lead to a concept"""
        causes = []
        queue = [(concept, [], 1.0, 0)]
        visited = set()
        
        while queue:
            current, path, confidence, depth = queue.pop(0)
            
            if current in visited or depth >= max_depth:
                continue
            
            visited.add(current)
            
            # Find direct causes
            for relation in relations:
                if self._concepts_match(relation.effect, current):
                    new_path = [relation] + path
                    causes.append((relation.cause, new_path))
                    
                    # Continue searching
                    queue.append((
                        relation.cause,
                        new_path,
                        confidence * relation.confidence,
                        depth + 1
                    ))
        
        return causes
    
    def infer_implicit_requirements(
        self,
        explicit_requirement: str,
        relations: List[CausalRelation]
    ) -> List[Dict]:
        """Infer implicit requirements from explicit ones"""
        implicit = []
        
        # Find what the explicit requirement requires
        effects = self.find_all_effects(explicit_requirement, relations, max_depth=2)
        
        for effect, path in effects:
            # Check if this is a requirement relation
            if any(r.relation_type == CausalRelationType.REQUIRES for r in path):
                implicit.append({
                    "requirement": effect,
                    "reasoning": self._build_reasoning_path(path),
                    "confidence": self._calculate_path_confidence(path),
                    "path_length": len(path)
                })
        
        # Sort by confidence
        implicit.sort(key=lambda x: x["confidence"], reverse=True)
        
        return implicit
    
    def analyze_dependencies(
        self,
        concept: str,
        relations: List[CausalRelation]
    ) -> Dict:
        """Analyze all dependencies for a concept"""
        
        # Find prerequisites (what's needed)
        prerequisites = self.find_all_causes(concept, relations, max_depth=3)
        
        # Find consequences (what it enables)
        consequences = self.find_all_effects(concept, relations, max_depth=3)
        
        # Find blockers (what prevents it)
        blockers = [
            (cause, path) for cause, path in prerequisites
            if any(r.relation_type == CausalRelationType.PREVENTS for r in path)
        ]
        
        return {
            "concept": concept,
            "prerequisites": [
                {
                    "requirement": cause,
                    "path": self._build_reasoning_path(path),
                    "confidence": self._calculate_path_confidence(path)
                }
                for cause, path in prerequisites[:5]
            ],
            "consequences": [
                {
                    "result": effect,
                    "path": self._build_reasoning_path(path),
                    "confidence": self._calculate_path_confidence(path)
                }
                for effect, path in consequences[:5]
            ],
            "blockers": [
                {
                    "blocker": cause,
                    "path": self._build_reasoning_path(path)
                }
                for cause, path in blockers
            ]
        }
    
    def _clean_concept(self, text: str) -> str:
        """Clean extracted concept text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove trailing punctuation
        text = re.sub(r'[،,;:.]+$', '', text)
        
        return text
    
    def _concepts_match(self, concept1: str, concept2: str, threshold: float = 0.7) -> bool:
        """Check if two concepts match (fuzzy matching)"""
        c1 = concept1.lower().strip()
        c2 = concept2.lower().strip()
        
        # Exact match
        if c1 == c2:
            return True
        
        # One contains the other
        if c1 in c2 or c2 in c1:
            return True
        
        # Jaccard similarity
        words1 = set(c1.split())
        words2 = set(c2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        
        return similarity >= threshold
    
    def _build_reasoning_path(self, path: List[CausalRelation]) -> str:
        """Build human-readable reasoning path"""
        if not path:
            return ""
        
        steps = []
        for i, relation in enumerate(path, 1):
            arrow = "→" if relation.relation_type != CausalRelationType.PREVENTS else "⊗"
            steps.append(f"{i}. {relation.cause} {arrow} {relation.effect}")
        
        return "\n".join(steps)
    
    def _calculate_path_confidence(self, path: List[CausalRelation]) -> float:
        """Calculate confidence for a path"""
        if not path:
            return 0.0
        
        confidence = 1.0
        for relation in path:
            confidence *= relation.confidence
        
        return confidence
    
    def visualize_causal_graph(
        self,
        relations: List[CausalRelation],
        max_nodes: int = 20
    ) -> Dict:
        """Create a graph visualization of causal relations"""
        nodes = set()
        edges = []
        
        for relation in relations[:max_nodes]:
            nodes.add(relation.cause)
            nodes.add(relation.effect)
            
            edges.append({
                "from": relation.cause,
                "to": relation.effect,
                "type": relation.relation_type.value,
                "confidence": relation.confidence,
                "source": relation.source_law
            })
        
        return {
            "nodes": [{"id": node, "label": node} for node in nodes],
            "edges": edges
        }
