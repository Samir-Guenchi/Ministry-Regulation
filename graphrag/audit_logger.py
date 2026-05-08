"""
Enterprise Audit Logging System for Ministry-Level Compliance

Features:
- Comprehensive query logging
- User activity tracking
- Performance metrics
- Security event logging
- Compliance reporting
- Data retention policies
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import uuid


class EventType(Enum):
    """Types of audit events"""
    QUERY = "query"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    BLOCKED_QUERY = "blocked_query"
    ERROR = "error"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"


class SeverityLevel(Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event"""
    event_id: str
    timestamp: str
    event_type: EventType
    severity: SeverityLevel
    user_id: Optional[str]
    session_id: Optional[str]
    query: Optional[str]
    query_hash: Optional[str]
    detected_language: Optional[str]
    response_language: Optional[str]
    retrieval_method: Optional[str]
    processing_time_ms: Optional[float]
    cached: bool
    confidence_score: Optional[float]
    num_citations: int
    blocked_reason: Optional[str]
    error_message: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Dict[str, Any]


class AuditLogger:
    """
    Enterprise audit logging system
    
    Provides:
    - Structured logging
    - Compliance tracking
    - Performance monitoring
    - Security auditing
    - Retention management
    """
    
    def __init__(self, log_directory: str = "./logs"):
        self.log_dir = Path(log_directory)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create separate log files
        self.audit_log_path = self.log_dir / "audit.jsonl"
        self.query_log_path = self.log_dir / "queries.jsonl"
        self.security_log_path = self.log_dir / "security.jsonl"
        self.performance_log_path = self.log_dir / "performance.jsonl"
        
        # Initialize Python logger
        self.logger = logging.getLogger("AuditLogger")
        self.logger.setLevel(logging.INFO)
        
        # File handler for audit log
        handler = logging.FileHandler(self.audit_log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        
        # Session tracking
        self.current_session_id = str(uuid.uuid4())
        
        # Log system start
        self.log_system_event("system_start", "System initialized")
    
    def _hash_query(self, query: str) -> str:
        """Create hash of query for privacy"""
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def _anonymize_query(self, query: str, level: str = "partial") -> str:
        """Anonymize query for privacy compliance"""
        if level == "full":
            return self._hash_query(query)
        elif level == "partial":
            # Keep first and last 20 characters
            if len(query) > 50:
                return f"{query[:20]}...{query[-20:]}"
            return query
        return query
    
    def log_query(
        self,
        query: str,
        detected_language: str,
        response_language: str,
        retrieval_method: str,
        processing_time_ms: float,
        cached: bool,
        confidence_score: float,
        num_citations: int,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log a query event"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            event_type=EventType.CACHE_HIT if cached else EventType.QUERY,
            severity=SeverityLevel.INFO,
            user_id=user_id,
            session_id=self.current_session_id,
            query=self._anonymize_query(query, level="partial"),
            query_hash=self._hash_query(query),
            detected_language=detected_language,
            response_language=response_language,
            retrieval_method=retrieval_method,
            processing_time_ms=processing_time_ms,
            cached=cached,
            confidence_score=confidence_score,
            num_citations=num_citations,
            blocked_reason=None,
            error_message=None,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
        
        self._write_event(event, self.query_log_path)
        self._write_event(event, self.audit_log_path)
        
        # Log to performance log if slow
        if processing_time_ms > 2000:
            self._write_event(event, self.performance_log_path)
    
    def log_blocked_query(
        self,
        query: str,
        reason: str,
        detected_language: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log a blocked query (security event)"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            event_type=EventType.BLOCKED_QUERY,
            severity=SeverityLevel.WARNING,
            user_id=user_id,
            session_id=self.current_session_id,
            query=self._anonymize_query(query, level="partial"),
            query_hash=self._hash_query(query),
            detected_language=detected_language,
            response_language=None,
            retrieval_method=None,
            processing_time_ms=None,
            cached=False,
            confidence_score=None,
            num_citations=0,
            blocked_reason=reason,
            error_message=None,
            ip_address=ip_address,
            user_agent=None,
            metadata=metadata or {}
        )
        
        self._write_event(event, self.security_log_path)
        self._write_event(event, self.audit_log_path)
    
    def log_error(
        self,
        error_message: str,
        query: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log an error event"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            event_type=EventType.ERROR,
            severity=SeverityLevel.ERROR,
            user_id=user_id,
            session_id=self.current_session_id,
            query=self._anonymize_query(query, level="full") if query else None,
            query_hash=self._hash_query(query) if query else None,
            detected_language=None,
            response_language=None,
            retrieval_method=None,
            processing_time_ms=None,
            cached=False,
            confidence_score=None,
            num_citations=0,
            blocked_reason=None,
            error_message=error_message,
            ip_address=None,
            user_agent=None,
            metadata=metadata or {}
        )
        
        self._write_event(event, self.audit_log_path)
    
    def log_system_event(self, event_type: str, message: str, metadata: Optional[Dict] = None):
        """Log a system event"""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "message": message,
            "session_id": self.current_session_id,
            "metadata": metadata or {}
        }
        
        self._write_json(event, self.audit_log_path)
    
    def _write_event(self, event: AuditEvent, log_path: Path):
        """Write event to log file"""
        event_dict = asdict(event)
        event_dict['event_type'] = event.event_type.value
        event_dict['severity'] = event.severity.value
        self._write_json(event_dict, log_path)
    
    def _write_json(self, data: Dict, log_path: Path):
        """Write JSON line to log file"""
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write to log: {e}")
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        stats = {
            "total_queries": 0,
            "cached_queries": 0,
            "blocked_queries": 0,
            "errors": 0,
            "avg_processing_time_ms": 0,
            "languages": {},
            "retrieval_methods": {},
            "confidence_scores": [],
            "time_period_hours": hours
        }
        
        try:
            processing_times = []
            
            with open(self.query_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event['timestamp'])
                        
                        if event_time >= cutoff_time:
                            stats["total_queries"] += 1
                            
                            if event.get('cached'):
                                stats["cached_queries"] += 1
                            
                            # Language stats
                            lang = event.get('detected_language')
                            if lang:
                                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                            
                            # Retrieval method stats
                            method = event.get('retrieval_method')
                            if method:
                                stats["retrieval_methods"][method] = stats["retrieval_methods"].get(method, 0) + 1
                            
                            # Processing time
                            proc_time = event.get('processing_time_ms')
                            if proc_time:
                                processing_times.append(proc_time)
                            
                            # Confidence scores
                            conf = event.get('confidence_score')
                            if conf:
                                stats["confidence_scores"].append(conf)
                    
                    except json.JSONDecodeError:
                        continue
            
            # Calculate averages
            if processing_times:
                stats["avg_processing_time_ms"] = round(sum(processing_times) / len(processing_times), 2)
            
            if stats["confidence_scores"]:
                stats["avg_confidence"] = round(sum(stats["confidence_scores"]) / len(stats["confidence_scores"]), 3)
                stats["min_confidence"] = round(min(stats["confidence_scores"]), 3)
                stats["max_confidence"] = round(max(stats["confidence_scores"]), 3)
            
            # Cache hit rate
            if stats["total_queries"] > 0:
                stats["cache_hit_rate"] = round(stats["cached_queries"] / stats["total_queries"], 3)
            
            # Count blocked queries
            if self.security_log_path.exists():
                with open(self.security_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            event_time = datetime.fromisoformat(event['timestamp'])
                            if event_time >= cutoff_time:
                                stats["blocked_queries"] += 1
                        except:
                            continue
        
        except FileNotFoundError:
            pass
        
        return stats
    
    def get_compliance_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate compliance report for date range"""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        report = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": start_date,
                "end": end_date
            },
            "total_queries": 0,
            "blocked_queries": 0,
            "blocked_reasons": {},
            "unique_users": set(),
            "languages_used": {},
            "peak_usage_hour": None,
            "compliance_issues": []
        }
        
        try:
            hourly_usage = {}
            
            # Analyze query log
            with open(self.query_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event['timestamp'])
                        
                        if start <= event_time <= end:
                            report["total_queries"] += 1
                            
                            # Track users
                            user_id = event.get('user_id')
                            if user_id:
                                report["unique_users"].add(user_id)
                            
                            # Track languages
                            lang = event.get('detected_language')
                            if lang:
                                report["languages_used"][lang] = report["languages_used"].get(lang, 0) + 1
                            
                            # Track hourly usage
                            hour = event_time.hour
                            hourly_usage[hour] = hourly_usage.get(hour, 0) + 1
                    
                    except:
                        continue
            
            # Analyze security log
            if self.security_log_path.exists():
                with open(self.security_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            event_time = datetime.fromisoformat(event['timestamp'])
                            
                            if start <= event_time <= end:
                                report["blocked_queries"] += 1
                                
                                reason = event.get('blocked_reason', 'unknown')
                                report["blocked_reasons"][reason] = report["blocked_reasons"].get(reason, 0) + 1
                        
                        except:
                            continue
            
            # Calculate peak usage
            if hourly_usage:
                peak_hour = max(hourly_usage.items(), key=lambda x: x[1])
                report["peak_usage_hour"] = f"{peak_hour[0]:02d}:00 ({peak_hour[1]} queries)"
            
            # Convert set to count
            report["unique_users"] = len(report["unique_users"])
            
            # Check for compliance issues
            if report["blocked_queries"] > report["total_queries"] * 0.1:
                report["compliance_issues"].append({
                    "type": "high_block_rate",
                    "message": f"High block rate: {report['blocked_queries']} / {report['total_queries']} queries blocked"
                })
        
        except FileNotFoundError:
            report["error"] = "Log files not found"
        
        return report
    
    def cleanup_old_logs(self, days: int = 90):
        """Clean up logs older than specified days (data retention)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for log_path in [self.audit_log_path, self.query_log_path, self.security_log_path, self.performance_log_path]:
            if not log_path.exists():
                continue
            
            try:
                # Read all lines
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Filter recent lines
                recent_lines = []
                for line in lines:
                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if event_time >= cutoff_date:
                            recent_lines.append(line)
                    except:
                        continue
                
                # Write back
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.writelines(recent_lines)
                
                removed = len(lines) - len(recent_lines)
                self.logger.info(f"Cleaned up {removed} old entries from {log_path.name}")
            
            except Exception as e:
                self.logger.error(f"Error cleaning up {log_path.name}: {e}")
