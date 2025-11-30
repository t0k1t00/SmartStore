import numpy as np
import pandas as pd
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import logging

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix

from ..config import settings
from ..repository import repository

logger = logging.getLogger(__name__)


class IsolationForestDetector:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.contamination = settings.IFOREST_CONTAMINATION
        self.n_estimators = settings.IFOREST_N_ESTIMATORS
        self.model_path = Path(settings.ANOMALY_MODEL_FILE)
    
    def _load_data(self) -> pd.DataFrame:
        logger.info("Loading data for anomaly detection...")
        
        try:
            # Get repository statistics
            stats = repository.get_stats()
            keys = repository.get_all_keys()
            
            # Create synthetic dataset with features
            # In production, this would be real access logs
            data = []
            
            for i in range(1000):
                # Generate normal access patterns
                if np.random.random() > 0.1:  # 90% normal
                    data.append({
                        'access_frequency': np.random.normal(10, 2),  # requests/min
                        'key_size': np.random.normal(100, 20),  # bytes
                        'ttl': np.random.choice([60, 300, 3600, 86400]),
                        'hour_of_day': np.random.randint(0, 24),
                        'response_time': np.random.normal(5, 1),  # ms
                        'error_rate': np.random.normal(0.01, 0.005),
                        'cache_hit_rate': np.random.normal(0.8, 0.1),
                    })
                else:  # 10% anomalies
                    data.append({
                        'access_frequency': np.random.normal(100, 20),  # Spike!
                        'key_size': np.random.normal(1000, 200),  # Large!
                        'ttl': np.random.choice([1, 5, 10]),  # Very short
                        'hour_of_day': np.random.randint(0, 24),
                        'response_time': np.random.normal(50, 10),  # Slow!
                        'error_rate': np.random.normal(0.1, 0.02),  # High errors
                        'cache_hit_rate': np.random.normal(0.2, 0.1),  # Low hit rate
                    })
            
            df = pd.DataFrame(data)
            logger.info(f"Loaded {len(df)} samples for training")
            return df
        
        except Exception as e:
            logger.warning(f"Could not load real data, using synthetic: {e}")
            # Fallback
            data = []
            for i in range(1000):
                data.append({
                    'access_frequency': np.random.normal(10, 5),
                    'key_size': np.random.normal(100, 50),
                    'ttl': np.random.choice([60, 300, 3600]),
                    'hour_of_day': np.random.randint(0, 24),
                    'response_time': np.random.normal(5, 2),
                    'error_rate': np.random.normal(0.01, 0.01),
                    'cache_hit_rate': np.random.normal(0.8, 0.15),
                })
            return pd.DataFrame(data)
    
    def train(self) -> Dict:
        logger.info("Starting Isolation Forest training...")
        
        # Load data
        df = self._load_data()
        
        # Prepare features
        X = df.values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        logger.info(f"Training with contamination={self.contamination}, n_estimators={self.n_estimators}")
        
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples='auto',
            random_state=42,
            n_jobs=-1  # Use all CPU cores
        )
        
        self.model.fit(X_scaled)
        
        # Predict on training data for metrics
        predictions = self.model.predict(X_scaled)
        anomaly_count = np.sum(predictions == -1)
        
        metrics = {
            'total_samples': len(X),
            'anomalies_detected': int(anomaly_count),
            'anomaly_rate': float(anomaly_count / len(X)),
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'feature_count': X.shape[1]
        }
        
        logger.info(f"Training complete: detected {anomaly_count} anomalies ({metrics['anomaly_rate']:.2%})")
        return metrics
    
    def predict(self, features: Dict) -> Tuple[bool, float]:
        if self.model is None:
            self.load_model()
        
        # Convert features to array
        feature_vector = np.array([[
            features['access_frequency'],
            features['key_size'],
            features['ttl'],
            features['hour_of_day'],
            features['response_time'],
            features['error_rate'],
            features['cache_hit_rate']
        ]])
        
        # Scale
        feature_vector_scaled = self.scaler.transform(feature_vector)
        
        # Predict
        prediction = self.model.predict(feature_vector_scaled)[0]
        score = self.model.score_samples(feature_vector_scaled)[0]
        
        is_anomaly = (prediction == -1)
        
        return is_anomaly, float(score)
    
    def detect_batch(self, features_list: List[Dict]) -> List[Tuple[bool, float]]:
        if self.model is None:
            self.load_model()
        
        # Convert to array
        X = np.array([[
            f['access_frequency'],
            f['key_size'],
            f['ttl'],
            f['hour_of_day'],
            f['response_time'],
            f['error_rate'],
            f['cache_hit_rate']
        ] for f in features_list])
        
        # Scale and predict
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        
        results = [
            (pred == -1, float(score))
            for pred, score in zip(predictions, scores)
        ]
        
        return results
    
    def save_model(self):
        logger.info(f"Saving model to {self.model_path}")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info("Model saved successfully")
    
    def load_model(self):
        logger.info(f"Loading model from {self.model_path}")
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        with open(self.model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.contamination = model_data['contamination']
        self.n_estimators = model_data['n_estimators']
        
        logger.info("Model loaded successfully")
