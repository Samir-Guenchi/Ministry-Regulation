"""
Build Knowledge Graph from existing JSON data
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graphrag.graph_builder import GraphBuilder
from graphrag.language_detector import LanguageDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_json_data(base_dir: str = "./Rag") -> list:
    """Load all JSON files from year directories"""
    all_documents = []
    
    years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]
    
    for year in years:
        year_dir = os.path.join(base_dir, year)
        if not os.path.exists(year_dir):
            logger.warning(f"Directory not found: {year_dir}")
            continue
        
        for filename in os.listdir(year_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(year_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    for item in data:
                        all_documents.append({
                            'title': item.get('title', ''),
                            'content': item.get('content', ''),
                            'year': year,
                            'file': filename
                        })
                    
                    logger.info(f"Loaded {len(data)} documents from {filename}")
                    
                except Exception as e:
                    logger.error(f"Error loading {filepath}: {e}")
    
    return all_documents


def build_knowledge_graph(documents: list):
    """Build knowledge graph from documents"""
    graph_builder = GraphBuilder()
    lang_detector = LanguageDetector()
    
    total_entities = 0
    total_relationships = 0
    
    logger.info(f"Processing {len(documents)} documents...")
    
    for i, doc in enumerate(documents):
        if i % 100 == 0:
            logger.info(f"Processed {i}/{len(documents)} documents")
        
        # Normalize text
        content = lang_detector.normalize_arabic(doc['content'])
        title = lang_detector.normalize_arabic(doc['title'])
        
        # Extract entities
        entities = graph_builder.extract_entities_from_text(
            content,
            title,
            doc['year']
        )
        
        if entities:
            # Add entities to graph
            count = graph_builder.add_entities(entities)
            total_entities += count
            
            # Extract and add relationships
            relationships = graph_builder.extract_relationships(content, entities)
            if relationships:
                rel_count = graph_builder.add_relationships(relationships)
                total_relationships += rel_count
    
    logger.info(f"Graph building complete!")
    logger.info(f"Total entities: {total_entities}")
    logger.info(f"Total relationships: {total_relationships}")
    
    graph_builder.close()


def main():
    """Main execution"""
    logger.info("Starting knowledge graph construction...")
    
    # Load documents
    documents = load_json_data()
    logger.info(f"Loaded {len(documents)} total documents")
    
    if not documents:
        logger.error("No documents found!")
        return
    
    # Build graph
    build_knowledge_graph(documents)
    
    logger.info("Knowledge graph construction complete!")


if __name__ == "__main__":
    main()
