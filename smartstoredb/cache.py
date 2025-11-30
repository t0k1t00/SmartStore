import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from collections import deque, defaultdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pickle
import os


class AccessPattern:
    def __init__(self, key: str, window_size: int = 100):
        self.key = key
        self.window_size = window_size
        self.access_times = deque(maxlen=window_size)
        self.access_intervals = deque(maxlen=window_size)
    
    def record_access(self, timestamp: datetime):
        if self.access_times:
            interval = (timestamp - self.access_times[-1]).total_seconds()
            self.access_intervals.append(interval)
        self.access_times.append(timestamp)
    
    def get_features(self) -> np.ndarray:
        if len(self.access_times) < 2:
            return np.array([0, 0, 0, 0])
        
        intervals = list(self.access_intervals)
        return np.array([
            len(intervals),  # Total accesses
            np.mean(intervals) if intervals else 0,  # Avg interval
            np.std(intervals) if len(intervals) > 1 else 0,  # Std deviation
            intervals[-1] if intervals else 0  # Last interval
        ])


class PredictiveCache:
    def __init__(self, cache_size: int = 1000, model_path: str = "./data/cache_model.pkl"):
        self.cache_size = cache_size
        self.model_path = model_path
        
        # Cache storage
        self.cache: Dict[str, any] = {}
        self.cache_access_order = deque()  # For LRU
        
        # Access pattern tracking
        self.patterns: Dict[str, AccessPattern] = {}
        
        # ML model components
        self.model = LinearRegression()
        self.scaler = StandardScaler()
        self.model_trained = False
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.predictions_made = 0
        
        # Load existing model if available
        self._load_model()
    
    def _load_model(self):
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data['model']
                    self.scaler = data['scaler']
                    self.model_trained = data['trained']
                print(" Loaded pre-trained cache model")
        except Exception as e:
            print(f" Could not load cache model: {e}")
    
    def _save_model(self):
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'trained': self.model_trained
                }, f)
        except Exception as e:
            print(f" Error saving cache model: {e}")
    
    def record_access(self, key: str, value: any = None):
        # Track access pattern
        if key not in self.patterns:
            self.patterns[key] = AccessPattern(key)
        self.patterns[key].record_access(datetime.now())
        
        # Update cache
        if key in self.cache:
            self.hits += 1
            # Move to end (most recently used)
            self.cache_access_order.remove(key)
            self.cache_access_order.append(key)
        else:
            self.misses += 1
            if value is not None:
                self._add_to_cache(key, value)
    
    def _add_to_cache(self, key: str, value: any):
        # Evict if cache is full
        if len(self.cache) >= self.cache_size:
            evict_key = self.cache_access_order.popleft()
            del self.cache[evict_key]
        
        self.cache[key] = value
        self.cache_access_order.append(key)
    
    def get_from_cache(self, key: str) -> Optional[any]:
        if key in self.cache:
            # Move to end (most recently used)
            self.cache_access_order.remove(key)
            self.cache_access_order.append(key)
            return self.cache[key]
        return None
    
    def train_model(self, min_samples: int = 50):
        # Collect training data
        X_train = []
        y_train = []
        
        for key, pattern in self.patterns.items():
            if len(pattern.access_times) >= 10:  # Minimum history
                features = pattern.get_features()
                # Predict next access likelihood (normalized)
                target = 1.0 if len(pattern.access_times) > 50 else 0.5
                X_train.append(features)
                y_train.append(target)
        
        if len(X_train) < min_samples:
            print(f" Not enough data to train (need {min_samples}, have {len(X_train)})")
            return False
        
        try:
            X_train = np.array(X_train)
            y_train = np.array(y_train)
            
            # Normalize features
            X_scaled = self.scaler.fit_transform(X_train)
            
            # Train model
            self.model.fit(X_scaled, y_train)
            self.model_trained = True
            
            # Save model
            self._save_model()
            
            print(f" Cache model trained on {len(X_train)} patterns")
            return True
        except Exception as e:
            print(f" Error training model: {e}")
            return False
    
    def predict_access_likelihood(self, key: str) -> float:
        if not self.model_trained or key not in self.patterns:
            return 0.5  # Default neutral prediction
        
        try:
            features = self.patterns[key].get_features().reshape(1, -1)
            features_scaled = self.scaler.transform(features)
            prediction = self.model.predict(features_scaled)[0]
            self.predictions_made += 1
            return max(0.0, min(1.0, prediction))
        except Exception as e:
            return 0.5
    
    def get_hot_keys(self, top_n: int = 10) -> List[Tuple[str, float]]:
        predictions = []
        for key in self.patterns.keys():
            likelihood = self.predict_access_likelihood(key)
            predictions.append((key, likelihood))
        
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions[:top_n]
    
    def get_cold_keys(self, threshold: float = 0.3) -> List[str]:
        cold_keys = []
        for key in self.patterns.keys():
            likelihood = self.predict_access_likelihood(key)
            if likelihood < threshold:
                cold_keys.append(key)
        return cold_keys
    
    def get_cache_stats(self) -> dict:
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'max_cache_size': self.cache_size,
            'cache_utilization': len(self.cache) / self.cache_size * 100,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': round(hit_rate, 2),
            'patterns_tracked': len(self.patterns),
            'predictions_made': self.predictions_made,
            'model_trained': self.model_trained
        }
    
    def optimize_cache(self, storage_engine) -> int:
        hot_keys = self.get_hot_keys(top_n=min(50, self.cache_size))
        loaded = 0
        
        for key, likelihood in hot_keys:
            if key not in self.cache:
                value = storage_engine.get(key)
                if value is not None:
                    self._add_to_cache(key, value)
                    loaded += 1
        
        return loaded
    
    def clear_cache(self):
        count = len(self.cache)
        self.cache.clear()
        self.cache_access_order.clear()
        return count
