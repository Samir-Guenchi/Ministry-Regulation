"""
Build Vector Store from existing JSON data
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from graphrag.config import settings
from graphrag.language_detector import LanguageDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_documents(base_dir: str = "./Rag") -> list:
    """Load all documents from JSON files"""
    all_documents = []
    lang_detector = LanguageDetector()
    
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
                        # Normalize text
                        content = lang_detector.normalize_arabic(item.get('content', ''))
                        title = lang_detector.normalize_arabic(item.get('title', ''))
                        
                        if len(content) > 50:  # Filter short content
                            doc = Document(
                                page_content=content,
                                metadata={
                                    'title': title,
                                    'year': year,
                                    'file': filename,
                                    'source': filepath
                                }
                            )
                            all_documents.append(doc)
                    
                    logger.info(f"Loaded {len(data)} documents from {filename}")
                    
                except Exception as e:
                    logger.error(f"Error loading {filepath}: {e}")
    
    return all_documents


def build_vector_store(documents: list, persist_directory: str = "./vector_store"):
    """Build and persist vector store"""
    logger.info(f"Building vector store with {len(documents)} documents...")
    
    # Initialize embeddings
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key
    )
    
    # Create vector store
    vector_store = FAISS.from_documents(documents, embeddings)
    
    # Save to disk
    vector_store.save_local(persist_directory)
    
    logger.info(f"Vector store saved to {persist_directory}")


def main():
    """Main execution"""
    logger.info("Starting vector store construction...")
    
    # Load documents
    documents = load_documents()
    logger.info(f"Loaded {len(documents)} total documents")
    
    if not documents:
        logger.error("No documents found!")
        return
    
    # Build vector store
    build_vector_store(documents)
    
    logger.info("Vector store construction complete!")


if __name__ == "__main__":
    main()
