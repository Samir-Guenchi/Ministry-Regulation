"""
Startup script for Groq-powered GraphRAG system
Performs system checks and starts the API server
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from graphrag.config import settings
from graphrag.cache_manager import SemanticCacheManager
import logging

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_groq_api():
    """Check Groq API connection"""
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        
        # Test connection
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10
        )
        
        logger.info("✓ Groq API connection successful")
        return True
    except Exception as e:
        logger.error(f"✗ Groq API connection failed: {e}")
        return False


def check_data_directory():
    """Check data directory exists and has files"""
    data_dir = Path(settings.data_directory)
    
    if not data_dir.exists():
        logger.warning(f"✗ Data directory not found: {data_dir}")
        logger.info(f"Creating data directory: {data_dir}")
        data_dir.mkdir(parents=True, exist_ok=True)
        return False
    
    # Count files
    json_files = list(data_dir.rglob("*.json"))
    txt_files = list(data_dir.rglob("*.txt"))
    pdf_files = list(data_dir.rglob("*.pdf"))
    
    total_files = len(json_files) + len(txt_files) + len(pdf_files)
    
    if total_files == 0:
        logger.warning(f"✗ No documents found in data directory")
        logger.info(f"Please add legal documents to: {data_dir}")
        return False
    
    logger.info(f"✓ Data directory found with {total_files} files")
    logger.info(f"  - JSON: {len(json_files)}")
    logger.info(f"  - TXT: {len(txt_files)}")
    logger.info(f"  - PDF: {len(pdf_files)}")
    return True


def check_cache_directory():
    """Check cache directory"""
    cache_dir = Path(settings.cache_directory)
    
    if not cache_dir.exists():
        logger.info(f"Creating cache directory: {cache_dir}")
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"✓ Cache directory ready: {cache_dir}")
    return True


def check_embeddings():
    """Check OpenAI API for embeddings"""
    if not settings.openai_api_key:
        logger.warning("✗ No OpenAI API key found")
        logger.warning("  Semantic cache will not work without embeddings")
        logger.info("  Set OPENAI_API_KEY in .env file")
        return False
    
    try:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key
        )
        
        # Test embedding
        test_embedding = embeddings.embed_query("test")
        
        logger.info("✓ OpenAI embeddings available")
        return True
    except Exception as e:
        logger.error(f"✗ OpenAI embeddings failed: {e}")
        return False


def initialize_cache():
    """Initialize semantic cache"""
    try:
        cache = SemanticCacheManager()
        stats = cache.get_stats()
        
        logger.info(f"✓ Semantic cache initialized")
        logger.info(f"  - Entries: {stats.get('total_entries', 0)}")
        logger.info(f"  - Size: {stats.get('cache_size_mb', 0)} MB")
        logger.info(f"  - Threshold: {stats.get('similarity_threshold', 0.90)}")
        return True
    except Exception as e:
        logger.error(f"✗ Cache initialization failed: {e}")
        return False


def print_configuration():
    """Print system configuration"""
    logger.info("\n" + "="*60)
    logger.info("System Configuration")
    logger.info("="*60)
    logger.info(f"LLM Provider: Groq")
    logger.info(f"Model: {settings.groq_model}")
    logger.info(f"Data Directory: {settings.data_directory}")
    logger.info(f"Cache Directory: {settings.cache_directory}")
    logger.info(f"Similarity Threshold: {settings.similarity_threshold}")
    logger.info(f"Force JSON Output: {settings.force_json_output}")
    logger.info(f"Political Filter: {settings.enable_political_filter}")
    logger.info(f"Block Out of Scope: {settings.block_out_of_scope}")
    logger.info("="*60 + "\n")


def main():
    """Main startup routine"""
    print("\n" + "="*60)
    print("Ministry Regulation GraphRAG System (Groq-Powered)")
    print("Version 2.1.0")
    print("="*60 + "\n")
    
    logger.info("Starting system checks...")
    
    # Run checks
    checks = {
        "Groq API": check_groq_api(),
        "Data Directory": check_data_directory(),
        "Cache Directory": check_cache_directory(),
        "Embeddings": check_embeddings(),
        "Semantic Cache": initialize_cache()
    }
    
    # Print results
    print("\nSystem Check Results:")
    print("-" * 60)
    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{check_name:.<40} {status}")
    print("-" * 60)
    
    # Check if critical components are ready
    critical_checks = ["Groq API", "Cache Directory"]
    all_critical_passed = all(checks[check] for check in critical_checks)
    
    if not all_critical_passed:
        print("\n✗ Critical checks failed. Please fix the issues above.")
        print("\nTroubleshooting:")
        if not checks["Groq API"]:
            print("  - Check GROQ_API_KEY in .env file")
            print("  - Verify API key is valid")
        sys.exit(1)
    
    # Warnings for non-critical components
    if not checks["Data Directory"]:
        print("\n⚠ Warning: No documents found in data directory")
        print(f"  Add legal documents to: {settings.data_directory}")
    
    if not checks["Embeddings"]:
        print("\n⚠ Warning: Embeddings not available")
        print("  Semantic cache will not work")
        print("  Set OPENAI_API_KEY in .env file")
    
    # Print configuration
    print_configuration()
    
    # Start API server
    print("Starting API server...")
    print("API will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        import uvicorn
        uvicorn.run(
            "graphrag.api:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.environment == "development",
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
