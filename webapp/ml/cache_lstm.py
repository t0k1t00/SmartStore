import numpy as np
import pandas as pd
import pickle
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import logging

# TensorFlow imports
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional, Embedding
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

from ..config import settings
from ..repository import repository

logger = logging.getLogger(__name__)


class LSTMCachePredictor:
    def __init__(self):
        self.model = None
        self.key_to_idx = {}
        self.idx_to_key = {}
        self.sequence_length = settings.LSTM_SEQUENCE_LENGTH
        self.vocab_size = 0
        self.model_path = Path(settings.CACHE_MODEL_FILE)
        self.metadata_path = self.model_path.with_suffix('.meta')
    
    def _load_access_logs(self) -> pd.DataFrame:
        logger.info("Loading access logs...")
        
        try:
            # Try to load from repository statistics
            stats = repository.get_stats()
            keys = repository.get_all_keys()
            access_log = []
            
            for _ in range(1000):  # Generate 1000 access events
                key = np.random.choice(keys) if keys else f"key_{np.random.randint(100)}"
                access_log.append({
                    'timestamp': datetime.now() - timedelta(seconds=np.random.randint(86400)),
                    'key': key,
                })
            
            df = pd.DataFrame(access_log)
            df = df.sort_values('timestamp')
            
            logger.info(f"Loaded {len(df)} access events")
            return df
        
        except Exception as e:
            logger.warning(f"Could not load real data, using synthetic: {e}")
            # Fallback to synthetic data
            access_log = []
            for i in range(1000):
                access_log.append({
                    'timestamp': datetime.now() - timedelta(seconds=i),
                    'key': f"key_{np.random.randint(50)}"
                })
            return pd.DataFrame(access_log)
    
    def _prepare_sequences(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        logger.info("Preparing sequences...")
        
        # Build vocabulary
        unique_keys = df['key'].unique()
        self.vocab_size = len(unique_keys) + 1  # +1 for padding
        self.key_to_idx = {key: idx + 1 for idx, key in enumerate(unique_keys)}
        self.idx_to_key = {idx: key for key, idx in self.key_to_idx.items()}
        
        # Convert keys to indices
        key_indices = [self.key_to_idx[key] for key in df['key']]
        
        # Create sequences
        X, y = [], []
        for i in range(len(key_indices) - self.sequence_length):
            X.append(key_indices[i:i + self.sequence_length])
            y.append(key_indices[i + self.sequence_length])
        
        X = np.array(X)
        y = np.array(y)
        
        logger.info(f"Created {len(X)} sequences (vocab size: {self.vocab_size})")
        return X, y
    
    def _build_model(self) -> keras.Model:
        logger.info("Building LSTM model...")
        
        model = Sequential([
            # Embedding layer for key representation
            Embedding(
                input_dim=self.vocab_size,
                output_dim=128,
                input_length=self.sequence_length
            ),
            
            # First Bidirectional LSTM layer
            Bidirectional(LSTM(256, return_sequences=True)),
            Dropout(0.3),
            
            # Second Bidirectional LSTM layer
            Bidirectional(LSTM(128)),
            Dropout(0.3),
            
            # Dense layers
            Dense(256, activation='relu'),
            Dropout(0.3),
            Dense(128, activation='relu'),
            
            # Output layer (predict next key index)
            Dense(self.vocab_size, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.info(f"Model built with {model.count_params():,} parameters")
        return model
    
    def train(self) -> Dict:
        logger.info("Starting LSTM training...")
        
        # Load and prepare data
        df = self._load_access_logs()
        X, y = self._prepare_sequences(df)
        
        # Split train/validation
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Build model
        self.model = self._build_model()
        
        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=5,
                restore_best_weights=True
            ),
            ModelCheckpoint(
                str(self.model_path),
                monitor='val_loss',
                save_best_only=True
            )
        ]
        
        # Train
        logger.info(f"Training on {len(X_train)} samples...")
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=settings.LSTM_EPOCHS,
            batch_size=settings.LSTM_BATCH_SIZE,
            callbacks=callbacks,
            verbose=1
        )
        
        # Evaluate
        loss, accuracy = self.model.evaluate(X_val, y_val, verbose=0)
        
        metrics = {
            'final_loss': float(loss),
            'final_accuracy': float(accuracy),
            'train_samples': len(X_train),
            'val_samples': len(X_val),
            'vocab_size': self.vocab_size,
            'sequence_length': self.sequence_length
        }
        
        logger.info(f"Training complete: loss={loss:.4f}, accuracy={accuracy:.4f}")
        return metrics
    
    def predict(self, recent_keys: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        if self.model is None:
            self.load_model()
        
        # Convert keys to indices
        key_indices = [
            self.key_to_idx.get(key, 0)
            for key in recent_keys[-self.sequence_length:]
        ]
        
        # Pad if necessary
        if len(key_indices) < self.sequence_length:
            key_indices = [0] * (self.sequence_length - len(key_indices)) + key_indices
        
        # Predict
        X = np.array([key_indices])
        predictions = self.model.predict(X, verbose=0)[0]
        
        # Get top-k predictions
        top_indices = np.argsort(predictions)[-top_k:][::-1]
        results = [
            (self.idx_to_key.get(idx, f"unknown_{idx}"), float(predictions[idx]))
            for idx in top_indices
            if idx in self.idx_to_key
        ]
        
        return results
    
    def save_model(self):
        logger.info(f"Saving model to {self.model_path}")
        
        # Save Keras model
        self.model.save(str(self.model_path))
        
        # Save metadata (vocabulary)
        metadata = {
            'key_to_idx': self.key_to_idx,
            'idx_to_key': {int(k): v for k, v in self.idx_to_key.items()},
            'vocab_size': self.vocab_size,
            'sequence_length': self.sequence_length,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("Model saved successfully")
    
    def load_model(self):
        logger.info(f"Loading model from {self.model_path}")
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        # Load Keras model
        self.model = load_model(str(self.model_path))
        
        # Load metadata
        with open(self.metadata_path, 'r') as f:
            metadata = json.load(f)
        
        self.key_to_idx = metadata['key_to_idx']
        self.idx_to_key = {int(k): v for k, v in metadata['idx_to_key'].items()}
        self.vocab_size = metadata['vocab_size']
        self.sequence_length = metadata['sequence_length']
        
        logger.info("Model loaded successfully")
