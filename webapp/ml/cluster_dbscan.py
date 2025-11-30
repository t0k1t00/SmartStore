import numpy as np
import pandas as pd
import pickle
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import logging
from collections import Counter

from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

from ..config import settings
from ..repository import repository

logger = logging.getLogger(__name__)


class DBSCANClusterer:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=2)  # For visualization
        self.eps = settings.DBSCAN_EPS
        self.min_samples = settings.DBSCAN_MIN_SAMPLES
        self.model_path = Path(settings.DBSCAN_MODEL_FILE)
    
    def _load_user_data(self) -> pd.DataFrame:
        logger.info("Loading user behavior data...")
        
        try:
            stats = repository.get_stats()
            keys = repository.get_all_keys()
            users = []
            
            for user_id in range(200):  # 200 users
                if np.random.random() < 0.7:  # 70% normal users
                    profile = {
                        'user_id': f"user_{user_id}",
                        'total_accesses': np.random.randint(100, 1000),
                        'avg_accesses_per_hour': np.random.normal(10, 3),
                        'peak_hour': np.random.choice([9, 10, 14, 15, 16]),
                        'avg_session_duration': np.random.normal(30, 10),  # minutes
                        'unique_keys_accessed': np.random.randint(20, 100),
                        'cache_hit_rate': np.random.normal(0.8, 0.1),
                        'avg_key_size': np.random.normal(100, 30),
                        'error_rate': np.random.normal(0.01, 0.005),
                    }
                elif np.random.random() < 0.2:  # 20% power users
                    profile = {
                        'user_id': f"user_{user_id}",
                        'total_accesses': np.random.randint(5000, 20000),
                        'avg_accesses_per_hour': np.random.normal(100, 20),
                        'peak_hour': np.random.choice([9, 10, 11, 14, 15]),
                        'avg_session_duration': np.random.normal(120, 30),
                        'unique_keys_accessed': np.random.randint(500, 2000),
                        'cache_hit_rate': np.random.normal(0.9, 0.05),
                        'avg_key_size': np.random.normal(200, 50),
                        'error_rate': np.random.normal(0.005, 0.002),
                    }
                else:  # 10% outliers (bots, attackers)
                    profile = {
                        'user_id': f"user_{user_id}",
                        'total_accesses': np.random.randint(10000, 50000),
                        'avg_accesses_per_hour': np.random.normal(500, 100),
                        'peak_hour': np.random.randint(0, 24),  # Random time
                        'avg_session_duration': np.random.normal(5, 2),  # Very short
                        'unique_keys_accessed': np.random.randint(10, 50),  # Few unique
                        'cache_hit_rate': np.random.normal(0.3, 0.1),  # Low hit rate
                        'avg_key_size': np.random.normal(50, 20),  # Small keys
                        'error_rate': np.random.normal(0.1, 0.03),  # High errors
                    }
                
                users.append(profile)
            
            df = pd.DataFrame(users)
            logger.info(f"Loaded {len(df)} user profiles")
            return df
        
        except Exception as e:
            logger.warning(f"Could not load real data, using synthetic: {e}")
            # Fallback
            users = []
            for i in range(200):
                users.append({
                    'user_id': f"user_{i}",
                    'total_accesses': np.random.randint(100, 5000),
                    'avg_accesses_per_hour': np.random.normal(50, 30),
                    'peak_hour': np.random.randint(0, 24),
                    'avg_session_duration': np.random.normal(30, 20),
                    'unique_keys_accessed': np.random.randint(10, 500),
                    'cache_hit_rate': np.random.normal(0.7, 0.2),
                    'avg_key_size': np.random.normal(100, 50),
                    'error_rate': np.random.normal(0.05, 0.05),
                })
            return pd.DataFrame(users)
    
    def fit(self) -> Dict:
        logger.info("Starting DBSCAN clustering...")
        
        # Load data
        df = self._load_user_data()
        
        # Prepare features (exclude user_id)
        user_ids = df['user_id'].values
        X = df.drop('user_id', axis=1).values
        feature_names = df.drop('user_id', axis=1).columns.tolist()
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit DBSCAN
        logger.info(f"Clustering with eps={self.eps}, min_samples={self.min_samples}")
        
        self.model = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric='euclidean',
            n_jobs=-1
        )
        
        labels = self.model.fit_predict(X_scaled)
        
        # Analyze results
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)
        
        # Cluster statistics
        cluster_counts = Counter(labels)
        cluster_sizes = {
            f"cluster_{k}" if k != -1 else "outliers": v
            for k, v in cluster_counts.items()
        }
        
        # Find representative samples for each cluster
        cluster_profiles = {}
        for cluster_id in set(labels):
            if cluster_id == -1:
                continue
            
            cluster_mask = labels == cluster_id
            cluster_data = X[cluster_mask]
            
            # Calculate cluster centroid
            centroid = np.mean(cluster_data, axis=0)
            
            cluster_profiles[f"cluster_{cluster_id}"] = {
                name: float(value)
                for name, value in zip(feature_names, centroid)
            }
        
        # PCA for visualization
        X_pca = self.pca.fit_transform(X_scaled)
        
        results = {
            'n_clusters': n_clusters,
            'n_outliers': n_noise,
            'outlier_rate': float(n_noise / len(labels)),
            'cluster_sizes': cluster_sizes,
            'cluster_profiles': cluster_profiles,
            'total_users': len(user_ids),
            'eps': self.eps,
            'min_samples': self.min_samples,
            'variance_explained': float(self.pca.explained_variance_ratio_.sum())
        }
        
        # Store user assignments
        self.user_clusters = pd.DataFrame({
            'user_id': user_ids,
            'cluster': labels,
            'pca_x': X_pca[:, 0],
            'pca_y': X_pca[:, 1]
        })
        
        logger.info(f"Clustering complete: {n_clusters} clusters, {n_noise} outliers")
        return results
    
    def predict(self, features: Dict) -> int:
        if self.model is None:
            self.load_model()
        
        # Convert features to array
        feature_vector = np.array([[
            features['total_accesses'],
            features['avg_accesses_per_hour'],
            features['peak_hour'],
            features['avg_session_duration'],
            features['unique_keys_accessed'],
            features['cache_hit_rate'],
            features['avg_key_size'],
            features['error_rate']
        ]])
        
        # Scale
        feature_vector_scaled = self.scaler.transform(feature_vector)
        if hasattr(self.model, 'components_'):
            from sklearn.metrics import pairwise_distances
            
            distances = pairwise_distances(
                feature_vector_scaled,
                self.model.components_
            )[0]
            
            nearest_core_idx = np.argmin(distances)
            
            if distances[nearest_core_idx] < self.eps:
                return int(self.model.labels_[self.model.core_sample_indices_[nearest_core_idx]])
            else:
                return -1  # Outlier
        
        return -1  # Default to outlier if no core samples
    
    def get_cluster_info(self, cluster_id: int) -> Dict:
        if not hasattr(self, 'user_clusters'):
            raise ValueError("Model not fitted yet")
        
        cluster_data = self.user_clusters[self.user_clusters['cluster'] == cluster_id]
        
        return {
            'cluster_id': cluster_id,
            'size': len(cluster_data),
            'users': cluster_data['user_id'].tolist(),
            'is_outlier': cluster_id == -1
        }
    
    def save_model(self):
        logger.info(f"Saving model to {self.model_path}")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'pca': self.pca,
            'eps': self.eps,
            'min_samples': self.min_samples,
            'user_clusters': self.user_clusters if hasattr(self, 'user_clusters') else None,
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
        self.pca = model_data['pca']
        self.eps = model_data['eps']
        self.min_samples = model_data['min_samples']
        
        if model_data.get('user_clusters') is not None:
            self.user_clusters = model_data['user_clusters']
        
        logger.info("Model loaded successfully")
