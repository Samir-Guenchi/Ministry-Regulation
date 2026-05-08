"""
Monitoring and RAG Evaluation System

Features:
- Real-time performance monitoring
- RAG evaluation metrics
- System health checks
- Query analytics
"""
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QueryMetrics:
    """Metrics for a single query"""
    query_id: str
    question: str
    detected_language: str
    response_language: str
    processing_time_ms: float
    cached: bool
    retrieval_method: str
    num_citations: int
    num_retrieved_docs: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "question": self.question[:50],
            "detected_language": self.detected_language,
            "response_language": self.response_language,
            "processing_time_ms": self.processing_time_ms,
            "cached": self.cached,
            "retrieval_method": self.retrieval_method,
            "num_citations": self.num_citations,
            "num_retrieved_docs": self.num_retrieved_docs,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_mb": self.memory_used_mb,
            "disk_percent": self.disk_percent,
            "timestamp": self.timestamp.isoformat()
        }


class PerformanceMonitor:
    """Monitor system and query performance"""
    
    def __init__(self, metrics_dir: str = "./metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Query metrics storage
        self.query_metrics: List[QueryMetrics] = []
        self.system_metrics: List[SystemMetrics] = []
        
        # Aggregated stats
        self.total_queries = 0
        self.cached_queries = 0
        self.total_processing_time = 0.0
        self.language_counts = defaultdict(int)
        self.retrieval_method_counts = defaultdict(int)
        
        # Start time
        self.start_time = datetime.now()
    
    def record_query(self, metrics: QueryMetrics):
        """Record query metrics"""
        self.query_metrics.append(metrics)
        
        # Update aggregated stats
        self.total_queries += 1
        if metrics.cached:
            self.cached_queries += 1
        self.total_processing_time += metrics.processing_time_ms
        self.language_counts[metrics.detected_language] += 1
        self.retrieval_method_counts[metrics.retrieval_method] += 1
        
        logger.info(f"Query recorded: {metrics.query_id} ({metrics.processing_time_ms:.2f}ms)")
    
    def record_system_metrics(self):
        """Record current system metrics"""
        metrics = SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=psutil.virtual_memory().percent,
            memory_used_mb=psutil.virtual_memory().used / (1024 * 1024),
            disk_percent=psutil.disk_usage('/').percent
        )
        self.system_metrics.append(metrics)
        return metrics
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate averages
        avg_processing_time = (
            self.total_processing_time / self.total_queries 
            if self.total_queries > 0 else 0
        )
        
        cache_hit_rate = (
            self.cached_queries / self.total_queries 
            if self.total_queries > 0 else 0
        )
        
        # Recent queries (last 100)
        recent_queries = self.query_metrics[-100:]
        recent_avg_time = (
            sum(q.processing_time_ms for q in recent_queries) / len(recent_queries)
            if recent_queries else 0
        )
        
        return {
            "uptime_seconds": uptime,
            "total_queries": self.total_queries,
            "cached_queries": self.cached_queries,
            "cache_hit_rate": cache_hit_rate,
            "avg_processing_time_ms": avg_processing_time,
            "recent_avg_time_ms": recent_avg_time,
            "language_distribution": dict(self.language_counts),
            "retrieval_methods": dict(self.retrieval_method_counts),
            "queries_per_minute": self.total_queries / (uptime / 60) if uptime > 0 else 0
        }
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        summary = self.get_summary_stats()
        
        # System metrics
        if self.system_metrics:
            latest_system = self.system_metrics[-1]
            system_info = latest_system.to_dict()
        else:
            system_info = self.record_system_metrics().to_dict()
        
        # Query performance breakdown
        cached_times = [q.processing_time_ms for q in self.query_metrics if q.cached]
        uncached_times = [q.processing_time_ms for q in self.query_metrics if not q.cached]
        
        return {
            "summary": summary,
            "system": system_info,
            "performance": {
                "cached_avg_ms": sum(cached_times) / len(cached_times) if cached_times else 0,
                "uncached_avg_ms": sum(uncached_times) / len(uncached_times) if uncached_times else 0,
                "min_time_ms": min([q.processing_time_ms for q in self.query_metrics]) if self.query_metrics else 0,
                "max_time_ms": max([q.processing_time_ms for q in self.query_metrics]) if self.query_metrics else 0
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def save_metrics(self):
        """Save metrics to disk"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save query metrics
        query_file = self.metrics_dir / f"queries_{timestamp}.json"
        with open(query_file, 'w', encoding='utf-8') as f:
            json.dump(
                [q.to_dict() for q in self.query_metrics],
                f,
                ensure_ascii=False,
                indent=2
            )
        
        # Save performance report
        report_file = self.metrics_dir / f"report_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(
                self.get_performance_report(),
                f,
                ensure_ascii=False,
                indent=2
            )
        
        logger.info(f"Metrics saved to {self.metrics_dir}")


# Global monitor instance
monitor = PerformanceMonitor()
