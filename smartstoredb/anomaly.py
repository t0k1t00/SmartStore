from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque
import statistics


class Anomaly:
    def __init__(self, anomaly_type: str, severity: str, description: str, 
                 key: Optional[str] = None, metric: Optional[str] = None):
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.type = anomaly_type
        self.severity = severity  # low, medium, high
        self.description = description
        self.key = key
        self.metric = metric
        self.timestamp = datetime.now()
        self.resolved = False
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'description': self.description,
            'key': self.key,
            'metric': self.metric,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved
        }


class AnomalyDetector:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        
        # Metrics tracking
        self.access_rate_history = deque(maxlen=window_size)
        self.error_rate_history = deque(maxlen=window_size)
        self.latency_history = deque(maxlen=window_size)
        
        # Anomaly storage
        self.anomalies: List[Anomaly] = []
        
        # Thresholds
        self.spike_threshold = 3.0  # Standard deviations
        self.error_rate_threshold = 0.05  # 5% error rate
    
    def record_access(self, success: bool = True, latency_ms: float = 0):
        self.access_rate_history.append(1)
        self.error_rate_history.append(0 if success else 1)
        if latency_ms > 0:
            self.latency_history.append(latency_ms)
    
    def check_access_spike(self) -> Optional[Anomaly]:
        if len(self.access_rate_history) < 20:
            return None
        
        recent = list(self.access_rate_history)[-10:]
        historical = list(self.access_rate_history)[:-10]
        
        if not historical:
            return None
        
        try:
            hist_mean = statistics.mean(historical)
            hist_std = statistics.stdev(historical) if len(historical) > 1 else 0
            recent_mean = statistics.mean(recent)
            
            if hist_std > 0:
                z_score = (recent_mean - hist_mean) / hist_std
                
                if z_score > self.spike_threshold:
                    anomaly = Anomaly(
                        anomaly_type="spike",
                        severity="medium" if z_score < 5 else "high",
                        description=f"Access rate spike detected: {recent_mean:.1f}x normal rate",
                        metric="access_rate"
                    )
                    self.anomalies.append(anomaly)
                    return anomaly
        except:
            pass
        
        return None
    
    def check_error_rate(self) -> Optional[Anomaly]:
        if len(self.error_rate_history) < 10:
            return None
        
        recent_errors = list(self.error_rate_history)[-10:]
        error_rate = sum(recent_errors) / len(recent_errors)
        
        if error_rate > self.error_rate_threshold:
            anomaly = Anomaly(
                anomaly_type="error_rate",
                severity="high" if error_rate > 0.1 else "medium",
                description=f"Elevated error rate: {error_rate*100:.1f}% (threshold: {self.error_rate_threshold*100}%)",
                metric="error_rate"
            )
            self.anomalies.append(anomaly)
            return anomaly
        
        return None
    
    def check_latency_spike(self) -> Optional[Anomaly]:
        if len(self.latency_history) < 20:
            return None
        
        try:
            recent = list(self.latency_history)[-10:]
            historical = list(self.latency_history)[:-10]
            
            hist_mean = statistics.mean(historical)
            hist_std = statistics.stdev(historical) if len(historical) > 1 else 0
            recent_mean = statistics.mean(recent)
            
            if hist_std > 0 and hist_mean > 0:
                z_score = (recent_mean - hist_mean) / hist_std
                
                if z_score > self.spike_threshold:
                    anomaly = Anomaly(
                        anomaly_type="latency",
                        severity="medium" if z_score < 5 else "high",
                        description=f"High latency detected: {recent_mean:.1f}ms (avg: {hist_mean:.1f}ms)",
                        metric="latency"
                    )
                    self.anomalies.append(anomaly)
                    return anomaly
        except:
            pass
        
        return None
    
    def check_key_anomalies(self, storage_engine) -> List[Anomaly]:
        anomalies = []
        entries = storage_engine.get_all_entries()
        
        # Check for keys with unusual access patterns
        access_counts = [entry.access_count for entry in entries.values()]
        
        if len(access_counts) > 10:
            try:
                mean_access = statistics.mean(access_counts)
                std_access = statistics.stdev(access_counts)
                
                for key, entry in entries.items():
                    if std_access > 0:
                        z_score = (entry.access_count - mean_access) / std_access
                        
                        if z_score > 4:  # Unusual high access
                            anomaly = Anomaly(
                                anomaly_type="hot_key",
                                severity="low",
                                description=f"Unusual high access count: {entry.access_count} (avg: {mean_access:.0f})",
                                key=key,
                                metric="access_count"
                            )
                            anomalies.append(anomaly)
                        
                        elif entry.access_count == 0 and \
                             (datetime.now() - entry.created_at).days > 7:
                            anomaly = Anomaly(
                                anomaly_type="cold_key",
                                severity="low",
                                description=f"Key created {(datetime.now() - entry.created_at).days} days ago but never accessed",
                                key=key,
                                metric="access_count"
                            )
                            anomalies.append(anomaly)
            except:
                pass
        
        self.anomalies.extend(anomalies)
        return anomalies
    
    def run_full_check(self, storage_engine) -> List[Anomaly]:
        detected = []
        
        # System-level checks
        spike = self.check_access_spike()
        if spike:
            detected.append(spike)
        
        error = self.check_error_rate()
        if error:
            detected.append(error)
        
        latency = self.check_latency_spike()
        if latency:
            detected.append(latency)
        
        # Key-level checks
        key_anomalies = self.check_key_anomalies(storage_engine)
        detected.extend(key_anomalies)
        
        return detected
    
    def get_anomalies(self, severity: Optional[str] = None, 
                      unresolved_only: bool = True) -> List[Anomaly]:
        anomalies = self.anomalies
        
        if unresolved_only:
            anomalies = [a for a in anomalies if not a.resolved]
        
        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]
        
        return sorted(anomalies, key=lambda x: x.timestamp, reverse=True)
    
    def resolve_anomaly(self, anomaly_id: str) -> bool:
        for anomaly in self.anomalies:
            if anomaly.id == anomaly_id:
                anomaly.resolved = True
                return True
        return False
    
    def get_stats(self) -> dict:
        unresolved = [a for a in self.anomalies if not a.resolved]
        
        return {
            'total_anomalies': len(self.anomalies),
            'unresolved_anomalies': len(unresolved),
            'high_severity': len([a for a in unresolved if a.severity == 'high']),
            'medium_severity': len([a for a in unresolved if a.severity == 'medium']),
            'low_severity': len([a for a in unresolved if a.severity == 'low']),
            'recent_anomalies': len([a for a in self.anomalies 
                                    if (datetime.now() - a.timestamp).seconds < 300])
        }
