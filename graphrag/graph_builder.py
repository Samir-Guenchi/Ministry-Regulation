from neo4j import GraphDatabase
from typing import List, Dict, Any, Tuple
from graphrag.config import settings
from graphrag.models import GraphEntity, GraphRelationship
import re
import logging

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Build and manage Knowledge Graph in Neo4j"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        self._create_indexes()
    
    def close(self):
        """Close Neo4j connection"""
        self.driver.close()
    
    def _create_indexes(self):
        """Create indexes for better performance"""
        with self.driver.session() as session:
            # Create indexes
            session.run("CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.entity_id)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (a:Article) ON (a.entity_id)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (m:Ministry) ON (m.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (d:Date) ON (d.year)")
            
            # Create constraints
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Law) REQUIRE l.entity_id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Article) REQUIRE a.entity_id IS UNIQUE")
    
    def extract_entities_from_text(self, text: str, title: str, year: str) -> List[GraphEntity]:
        """
        Extract legal entities from Arabic text
        
        Entities:
        - Laws (قانون، مرسوم، قرار)
        - Articles (مادة، فصل، باب)
        - Ministries (وزارة)
        - Dates (years, dates)
        - Organizations (هيئة، مؤسسة، لجنة)
        """
        entities = []
        
        # Extract law references
        law_pattern = r'(قانون|مرسوم|قرار)\s+رقم\s+(\d+[\.\-]\d+)'
        for match in re.finditer(law_pattern, text):
            law_type = match.group(1)
            law_number = match.group(2)
            entity_id = f"law_{year}_{law_number.replace('.', '_').replace('-', '_')}"
            
            entities.append(GraphEntity(
                entity_id=entity_id,
                entity_type="Law",
                name=f"{law_type} رقم {law_number}",
                properties={
                    "law_type": law_type,
                    "law_number": law_number,
                    "year": year,
                    "title": title
                }
            ))
        
        # Extract article references
        article_pattern = r'(المادة|الفصل|الباب)\s+(\d+)'
        for match in re.finditer(article_pattern, text):
            article_type = match.group(1)
            article_number = match.group(2)
            entity_id = f"article_{year}_{article_number}"
            
            entities.append(GraphEntity(
                entity_id=entity_id,
                entity_type="Article",
                name=f"{article_type} {article_number}",
                properties={
                    "article_type": article_type,
                    "article_number": article_number,
                    "year": year
                }
            ))
        
        # Extract ministry references
        ministry_pattern = r'وزارة\s+([\w\s]+?)(?=\s+(?:و|أو|،|\.)|$)'
        for match in re.finditer(ministry_pattern, text):
            ministry_name = match.group(0).strip()
            entity_id = f"ministry_{hashlib.md5(ministry_name.encode()).hexdigest()[:8]}"
            
            entities.append(GraphEntity(
                entity_id=entity_id,
                entity_type="Ministry",
                name=ministry_name,
                properties={"full_name": ministry_name}
            ))
        
        # Extract organization references
        org_pattern = r'(هيئة|مؤسسة|لجنة|مجلس)\s+([\w\s]+?)(?=\s+(?:و|أو|،|\.)|$)'
        for match in re.finditer(org_pattern, text):
            org_name = match.group(0).strip()
            entity_id = f"org_{hashlib.md5(org_name.encode()).hexdigest()[:8]}"
            
            entities.append(GraphEntity(
                entity_id=entity_id,
                entity_type="Organization",
                name=org_name,
                properties={"full_name": org_name}
            ))
        
        return entities
    
    def extract_relationships(self, text: str, entities: List[GraphEntity]) -> List[GraphRelationship]:
        """
        Extract relationships between entities
        
        Relationships:
        - REPEALS (يلغي، ألغى)
        - AMENDS (يعدل، عدل)
        - REFERENCES (يشير، أشار، بموجب)
        - ISSUED_BY (صادر عن)
        - APPLIES_TO (ينطبق على)
        """
        relationships = []
        
        # Extract repeal relationships
        repeal_pattern = r'(يلغي|ألغى|يلغى)\s+.*?(قانون|مرسوم|قرار)\s+رقم\s+(\d+[\.\-]\d+)'
        for match in re.finditer(repeal_pattern, text):
            # Find source and target entities
            for entity in entities:
                if entity.entity_type == "Law":
                    relationships.append(GraphRelationship(
                        source_id=entity.entity_id,
                        target_id=f"law_{match.group(3).replace('.', '_').replace('-', '_')}",
                        relationship_type="REPEALS",
                        properties={"context": match.group(0)}
                    ))
        
        # Extract amendment relationships
        amend_pattern = r'(يعدل|عدل|تعديل)\s+.*?(قانون|مرسوم|قرار)\s+رقم\s+(\d+[\.\-]\d+)'
        for match in re.finditer(amend_pattern, text):
            for entity in entities:
                if entity.entity_type == "Law":
                    relationships.append(GraphRelationship(
                        source_id=entity.entity_id,
                        target_id=f"law_{match.group(3).replace('.', '_').replace('-', '_')}",
                        relationship_type="AMENDS",
                        properties={"context": match.group(0)}
                    ))
        
        # Extract reference relationships
        reference_pattern = r'(بموجب|وفقا ل|طبقا ل|حسب)\s+.*?(قانون|مرسوم|قرار)\s+رقم\s+(\d+[\.\-]\d+)'
        for match in re.finditer(reference_pattern, text):
            for entity in entities:
                if entity.entity_type == "Law":
                    relationships.append(GraphRelationship(
                        source_id=entity.entity_id,
                        target_id=f"law_{match.group(3).replace('.', '_').replace('-', '_')}",
                        relationship_type="REFERENCES",
                        properties={"context": match.group(0)}
                    ))
        
        return relationships
    
    def add_entities(self, entities: List[GraphEntity]) -> int:
        """Add entities to graph"""
        count = 0
        with self.driver.session() as session:
            for entity in entities:
                try:
                    query = f"""
                    MERGE (e:{entity.entity_type} {{entity_id: $entity_id}})
                    SET e.name = $name,
                        e += $properties
                    RETURN e
                    """
                    session.run(query, 
                               entity_id=entity.entity_id,
                               name=entity.name,
                               properties=entity.properties)
                    count += 1
                except Exception as e:
                    logger.error(f"Error adding entity {entity.entity_id}: {e}")
        
        return count
    
    def add_relationships(self, relationships: List[GraphRelationship]) -> int:
        """Add relationships to graph"""
        count = 0
        with self.driver.session() as session:
            for rel in relationships:
                try:
                    query = f"""
                    MATCH (source {{entity_id: $source_id}})
                    MATCH (target {{entity_id: $target_id}})
                    MERGE (source)-[r:{rel.relationship_type}]->(target)
                    SET r += $properties
                    RETURN r
                    """
                    session.run(query,
                               source_id=rel.source_id,
                               target_id=rel.target_id,
                               properties=rel.properties)
                    count += 1
                except Exception as e:
                    logger.error(f"Error adding relationship {rel.source_id}->{rel.target_id}: {e}")
        
        return count
    
    def query_graph(self, entity_ids: List[str], max_depth: int = 2) -> Dict[str, Any]:
        """
        Query graph for related entities
        
        Args:
            entity_ids: Starting entity IDs
            max_depth: Maximum traversal depth
            
        Returns:
            Graph structure with nodes and relationships
        """
        with self.driver.session() as session:
            query = """
            MATCH path = (start)-[*1..%d]-(related)
            WHERE start.entity_id IN $entity_ids
            RETURN path
            LIMIT 50
            """ % max_depth
            
            result = session.run(query, entity_ids=entity_ids)
            
            nodes = []
            relationships = []
            
            for record in result:
                path = record['path']
                for node in path.nodes:
                    nodes.append({
                        'entity_id': node.get('entity_id'),
                        'name': node.get('name'),
                        'labels': list(node.labels),
                        'properties': dict(node)
                    })
                
                for rel in path.relationships:
                    relationships.append({
                        'type': rel.type,
                        'properties': dict(rel)
                    })
            
            return {
                'nodes': nodes,
                'relationships': relationships
            }


import hashlib
