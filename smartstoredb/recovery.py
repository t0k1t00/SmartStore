import os
import pickle
import threading
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum


class OperationType(Enum):
    PUT = "PUT"
    DELETE = "DELETE"
    CLEAR = "CLEAR"


class LogEntry:
    def __init__(self, operation: OperationType, key: str, 
                 value: any = None, metadata: dict = None):
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.timestamp = datetime.now()
        self.operation = operation
        self.key = key
        self.value = value
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'operation': self.operation.value,
            'key': self.key,
            'value': self.value,
            'metadata': self.metadata
        }


class RecoveryManager:
    def __init__(self, log_dir: str = "./data/wal"):
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "transaction.log")
        self.checkpoint_file = os.path.join(log_dir, "checkpoint.dat")
        
        # In-memory log buffer
        self.log_buffer: List[LogEntry] = []
        self.buffer_size = 100  # Flush after 100 operations
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Create log directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Recovery flag
        self.recovery_performed = False
    
    def log_operation(self, operation: OperationType, key: str, 
                     value: any = None, metadata: dict = None):
        with self.lock:
            entry = LogEntry(operation, key, value, metadata)
            self.log_buffer.append(entry)
            
            # Flush if buffer is full
            if len(self.log_buffer) >= self.buffer_size:
                self._flush_log()
    
    def _flush_log(self):
        if not self.log_buffer:
            return
        
        try:
            # Load existing log
            existing_log = []
            if os.path.exists(self.log_file):
                with open(self.log_file, 'rb') as f:
                    try:
                        existing_log = pickle.load(f)
                    except:
                        existing_log = []
            
            # Append new entries
            log_dicts = [entry.to_dict() for entry in self.log_buffer]
            existing_log.extend(log_dicts)
            
            # Save updated log
            with open(self.log_file, 'wb') as f:
                pickle.dump(existing_log, f)
            
            # Clear buffer
            self.log_buffer.clear()
            
        except Exception as e:
            print(f" Error flushing transaction log: {e}")
    
    def create_checkpoint(self, storage_engine):
        with self.lock:
            try:
                # Flush any pending log entries
                self._flush_log()
                
                # Save current state as checkpoint
                all_entries = storage_engine.get_all_entries()
                checkpoint_data = {
                    'timestamp': datetime.now().isoformat(),
                    'entries': {
                        key: entry.to_dict() 
                        for key, entry in all_entries.items()
                    }
                }
                
                with open(self.checkpoint_file, 'wb') as f:
                    pickle.dump(checkpoint_data, f)
                
                # Clear transaction log after successful checkpoint
                if os.path.exists(self.log_file):
                    os.remove(self.log_file)
                
                print(f" Checkpoint created with {len(all_entries)} keys")
                return True
            
            except Exception as e:
                print(f" Error creating checkpoint: {e}")
                return False
    
    def recover(self, storage_engine) -> bool:
        if self.recovery_performed:
            return False
        
        recovered = False
        
        try:
            # Load checkpoint if exists
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'rb') as f:
                    checkpoint_data = pickle.load(f)
                
                # Restore checkpoint state
                for key, entry_dict in checkpoint_data['entries'].items():
                    storage_engine.put(
                        key=entry_dict['key'],
                        value=entry_dict['value'],
                        ttl=entry_dict['ttl'],
                        data_type=entry_dict['data_type']
                    )
                
                print(f" Restored checkpoint ({len(checkpoint_data['entries'])} keys)")
                recovered = True
            
            # Replay transaction log
            if os.path.exists(self.log_file):
                with open(self.log_file, 'rb') as f:
                    try:
                        log_entries = pickle.load(f)
                    except:
                        log_entries = []
                
                if log_entries:
                    for entry_dict in log_entries:
                        op = entry_dict['operation']
                        key = entry_dict['key']
                        
                        if op == "PUT":
                            metadata = entry_dict.get('metadata', {})
                            storage_engine.put(
                                key=key,
                                value=entry_dict['value'],
                                ttl=metadata.get('ttl'),
                                data_type=metadata.get('data_type', 'string')
                            )
                        elif op == "DELETE":
                            storage_engine.delete(key)
                        elif op == "CLEAR":
                            storage_engine.clear_all()
                    
                    print(f" Replayed {len(log_entries)} log entries")
                    recovered = True
            
            self.recovery_performed = True
            
            if recovered:
                print(" Database recovery completed successfully")
            
            return recovered
        
        except Exception as e:
            print(f" Error during recovery: {e}")
            return False
    
    def get_log_stats(self) -> dict:
        stats = {
            'log_exists': os.path.exists(self.log_file),
            'checkpoint_exists': os.path.exists(self.checkpoint_file),
            'buffered_entries': len(self.log_buffer),
            'log_entries': 0,
            'log_size_bytes': 0,
            'checkpoint_size_bytes': 0,
            'recovery_performed': self.recovery_performed
        }
        
        try:
            if os.path.exists(self.log_file):
                stats['log_size_bytes'] = os.path.getsize(self.log_file)
                
                with open(self.log_file, 'rb') as f:
                    try:
                        log_entries = pickle.load(f)
                        stats['log_entries'] = len(log_entries)
                    except:
                        pass
            
            if os.path.exists(self.checkpoint_file):
                stats['checkpoint_size_bytes'] = os.path.getsize(self.checkpoint_file)
        except:
            pass
        
        return stats
    
    def clear_logs(self) -> bool:
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
            self.log_buffer.clear()
            print(" Transaction logs cleared")
            return True
        except Exception as e:
            print(f" Error clearing logs: {e}")
            return False
    
    def __del__(self):
        with self.lock:
            self._flush_log()
