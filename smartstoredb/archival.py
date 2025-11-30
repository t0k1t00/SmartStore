import gzip
import pickle
import os
from typing import Dict, List, Optional
from datetime import datetime
import shutil


class ArchivedEntry:
    def __init__(self, key: str, value: any, metadata: dict):
        self.key = key
        self.value = value
        self.metadata = metadata
        self.archived_at = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            'key': self.key,
            'value': self.value,
            'metadata': self.metadata,
            'archived_at': self.archived_at.isoformat()
        }


class ArchiveManager:
    def __init__(self, archive_dir: str = "./data/archive"):
        self.archive_dir = archive_dir
        self.archive_file = os.path.join(archive_dir, "archive.gz")
        self.index_file = os.path.join(archive_dir, "archive_index.pkl")
        
        # In-memory index of archived keys
        self.archive_index: Dict[str, dict] = {}
        
        # Create archive directory
        os.makedirs(archive_dir, exist_ok=True)
        
        # Load existing archive index
        self._load_index()
    
    def _load_index(self):
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, 'rb') as f:
                    self.archive_index = pickle.load(f)
                print(f" Loaded archive index ({len(self.archive_index)} entries)")
        except Exception as e:
            print(f" Could not load archive index: {e}")
    
    def _save_index(self):
        try:
            with open(self.index_file, 'wb') as f:
                pickle.dump(self.archive_index, f)
        except Exception as e:
            print(f"✗ Error saving archive index: {e}")
    
    def archive_keys(self, storage_engine, keys: List[str], 
                    remove_from_storage: bool = True) -> int:
        archived_count = 0
        archived_data = []
        
        # Load existing archive if it exists
        if os.path.exists(self.archive_file):
            try:
                with gzip.open(self.archive_file, 'rb') as f:
                    archived_data = pickle.load(f)
            except:
                archived_data = []
        
        # Archive each key
        for key in keys:
            entry = storage_engine.get_entry(key)
            if entry:
                # Create archived entry
                archived_entry = ArchivedEntry(
                    key=key,
                    value=entry.value,
                    metadata=entry.to_dict()
                )
                
                archived_data.append(archived_entry.to_dict())
                
                # Update index
                self.archive_index[key] = {
                    'archived_at': archived_entry.archived_at.isoformat(),
                    'size': len(str(entry.value)),
                    'data_type': entry.data_type
                }
                
                # Remove from active storage if requested
                if remove_from_storage:
                    storage_engine.delete(key)
                
                archived_count += 1
        
        # Save compressed archive
        try:
            with gzip.open(self.archive_file, 'wb', compresslevel=9) as f:
                pickle.dump(archived_data, f)
            
            self._save_index()
            
            print(f" Archived {archived_count} keys with compression")
        except Exception as e:
            print(f" Error saving archive: {e}")
            return 0
        
        return archived_count
    
    def restore_keys(self, storage_engine, keys: Optional[List[str]] = None) -> int:
        if not os.path.exists(self.archive_file):
            print(" No archive file found")
            return 0
        
        try:
            # Load archive
            with gzip.open(self.archive_file, 'rb') as f:
                archived_data = pickle.load(f)
            
            restored_count = 0
            remaining_data = []
            
            for entry_dict in archived_data:
                key = entry_dict['key']
                
                # Check if this key should be restored
                if keys is None or key in keys:
                    # Restore to storage
                    metadata = entry_dict['metadata']
                    storage_engine.put(
                        key=key,
                        value=entry_dict['value'],
                        ttl=metadata.get('ttl'),
                        data_type=metadata.get('data_type', 'string')
                    )
                    
                    # Remove from index
                    if key in self.archive_index:
                        del self.archive_index[key]
                    
                    restored_count += 1
                else:
                    remaining_data.append(entry_dict)
            
            # Save updated archive
            with gzip.open(self.archive_file, 'wb', compresslevel=9) as f:
                pickle.dump(remaining_data, f)
            
            self._save_index()
            
            print(f" Restored {restored_count} keys from archive")
            return restored_count
        
        except Exception as e:
            print(f" Error restoring from archive: {e}")
            return 0
    
    def list_archived_keys(self) -> List[dict]:
        return [
            {
                'key': key,
                **metadata
            }
            for key, metadata in self.archive_index.items()
        ]
    
    def get_archive_stats(self) -> dict:
        stats = {
            'archived_keys': len(self.archive_index),
            'archive_exists': os.path.exists(self.archive_file),
            'archive_size_bytes': 0,
            'archive_size_mb': 0,
            'compression_ratio': 0
        }
        
        if os.path.exists(self.archive_file):
            try:
                # Get compressed size
                compressed_size = os.path.getsize(self.archive_file)
                stats['archive_size_bytes'] = compressed_size
                stats['archive_size_mb'] = round(compressed_size / (1024 * 1024), 2)
                
                # Calculate compression ratio
                with gzip.open(self.archive_file, 'rb') as f:
                    archived_data = pickle.load(f)
                    
                # Estimate uncompressed size
                uncompressed_size = len(pickle.dumps(archived_data))
                if uncompressed_size > 0:
                    stats['compression_ratio'] = round(compressed_size / uncompressed_size, 2)
            except:
                pass
        
        return stats
    
    def archive_cold_keys(self, storage_engine, cache, 
                         threshold: float = 0.3, max_keys: int = 100) -> int:
        cold_keys = cache.get_cold_keys(threshold=threshold)
        
        # Limit number of keys to archive
        cold_keys = cold_keys[:max_keys]
        
        if not cold_keys:
            print(" No cold keys found for archival")
            return 0
        
        return self.archive_keys(storage_engine, cold_keys, remove_from_storage=True)
    
    def is_archived(self, key: str) -> bool:
        return key in self.archive_index
    
    def delete_archive(self) -> bool:
        try:
            if os.path.exists(self.archive_file):
                os.remove(self.archive_file)
            if os.path.exists(self.index_file):
                os.remove(self.index_file)
            self.archive_index.clear()
            print(" Archive deleted")
            return True
        except Exception as e:
            print(f" Error deleting archive: {e}")
            return False
