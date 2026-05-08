from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from graphrag.models import QueryRequest, QueryResponse, IngestRequest, IngestResponse
from graphrag.workflow import GraphRAGWorkflow
from graphrag.config import settings
import logging
import uvicorn
import json

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Ministry Regulation GraphRAG API (Groq-Powered)",
    description="High-production GraphRAG system for Arabic legal documents with Groq LLM",
    version="2.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize workflow
workflow = None

@app.on_event("startup")
async def startup_event():
    """Initialize workflow on startup"""
    global workflow
    try:
        workflow = GraphRAGWorkflow()
        workflow.retriever.load_vector_store()
        logger.info("GraphRAG workflow initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize workflow: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if workflow:
        workflow.retriever.close()
    logger.info("GraphRAG workflow shut down")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Ministry Regulation GraphRAG API (Groq-Powered)",
        "version": "2.1.0",
        "status": "running",
        "llm": settings.groq_model,
        "cache_type": "FAISS-based semantic cache",
        "data_source": settings.data_directory
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check cache connection
        cache_stats = workflow.cache.get_stats()
        
        return {
            "status": "healthy",
            "cache": {
                "connected": True,
                "stats": cache_stats
            },
            "workflow": "initialized"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Process legal query with Groq LLM
    
    Features:
    - Multilingual input (Arabic, English, French, Darija)
    - Darija → Standard Arabic response
    - Hybrid vector-graph retrieval
    - FAISS-based semantic caching (0.90 threshold)
    - JSON-enforced output
    - Safety guardrails (political filter, domain constraints)
    - Citation requirements
    """
    try:
        logger.info(f"Processing query: {request.question[:50]}...")
        
        # Process through workflow
        response = workflow.process_query(request)
        
        logger.info(f"Query processed in {response.processing_time_ms:.2f}ms (cached: {response.cached})")
        
        return response
        
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        
        # Return JSON error if enforcement is enabled
        if settings.force_json_output:
            error_response = {
                "error": "Processing error",
                "message": str(e)
            }
            raise HTTPException(status_code=500, detail=json.dumps(error_response))
        else:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """
    Ingest legal document
    
    Processes PDF documents and builds knowledge graph
    """
    try:
        # This would be implemented with async processing
        # For now, return a placeholder
        return IngestResponse(
            task_id="task_123",
            status="queued",
            message="Document queued for processing",
            documents_processed=0
        )
    except Exception as e:
        logger.error(f"Document ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    try:
        stats = workflow.cache.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/invalidate")
async def invalidate_cache():
    """Invalidate all cache entries"""
    try:
        count = workflow.cache.invalidate()
        return {"message": f"Invalidated {count} cache entries"}
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "graphrag.api:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development"
    )
