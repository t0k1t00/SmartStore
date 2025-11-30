import os
import pickle
import json
import time
import threading
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import portalocker


class KeyValueEntry:
    def __init__(self, key: str, value: Any, ttl: Optional[int] = None, 
                 data_type: str = "string"):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.data_type = data_type
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.last_accessed = datetime.now()
        self.access_count = 0
        self.expires_at = datetime.now() + timedelta(seconds=ttl) if ttl else None
    
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now() > self.expires_at
    
    def access(self):
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "ttl": self.ttl,
            "data_type": self.data_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


class StorageEngine:
    def __init__(self, data_dir: str = "./data"):

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        # Actual data file
        self.db_file = os.path.join(self.data_dir, "smartstore.db")

        # REQUIRED: File lock for portalocker
        self.lock_file = os.path.join(self.data_dir, "smartstore.lock")

        # In-memory key-value index
        self.index: Dict[str, KeyValueEntry] = {}

        # Local thread safety
        self.lock = threading.RLock()

        # Load from disk
        self._load_database()

        # Start background TTL cleanup
        threading.Thread(target=self._ttl_cleanup_loop, daemon=True).start()

    def _read_file_unsafe(self):
        if not os.path.exists(self.db_file):
            return {}

        try:
            with open(self.db_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}

    def _write_file_unsafe(self, data):
        with open(self.db_file, "wb") as f:
            pickle.dump(data, f)

    def _load_database(self):
        try:
            data = self._read_file_unsafe()
            for key, entry_dict in data.items():
                entry = KeyValueEntry(
                    key=entry_dict["key"],
                    value=entry_dict["value"],
                    ttl=entry_dict["ttl"],
                    data_type=entry_dict["data_type"]
                )

                # Restore metadata
                entry.created_at = datetime.fromisoformat(entry_dict["created_at"])
                entry.updated_at = datetime.fromisoformat(entry_dict["updated_at"])
                entry.last_accessed = datetime.fromisoformat(entry_dict["last_accessed"])
                entry.access_count = entry_dict["access_count"]

                if entry_dict["expires_at"]:
                    entry.expires_at = datetime.fromisoformat(entry_dict["expires_at"])

                # Skip expired keys
                if not entry.is_expired():
                    self.index[key] = entry

            print(f" Loaded {len(self.index)} keys from disk")

        except Exception as e:
            print(f" Warning: Failed to load DB: {e}")

    def _save_database(self):
        data = {key: entry.to_dict() for key, entry in self.index.items()}
        self._write_file_unsafe(data)

    def _ttl_cleanup_loop(self):
        while True:
            time.sleep(5)
            self.cleanup_expired()

    def cleanup_expired(self):
        with portalocker.Lock(self.lock_file, "w+", flags=portalocker.LOCK_EX):
            data = self._read_file_unsafe()
            removed = []

            for key, entry in list(data.items()):
                if entry["expires_at"]:
                    expires = datetime.fromisoformat(entry["expires_at"])
                    if expires < datetime.now():
                        removed.append(key)
                        del data[key]

            if removed:
                self._write_file_unsafe(data)

        with self.lock:
            for key in removed:
                self.index.pop(key, None)

        return removed

    def put(self, key: str, value: Any, ttl: Optional[int] = None,
            data_type: str = "string") -> bool:

        try:
            entry = KeyValueEntry(key, value, ttl, data_type)

            with self.lock:
                self.index[key] = entry
                self._save_database()

            return True

        except Exception as e:
            print(f" Error storing key '{key}': {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            entry = self.index.get(key)

            if not entry:
                return None

            if entry.is_expired():
                del self.index[key]
                self._save_database()
                return None

            entry.access()
            return entry.value

    def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.index:
                del self.index[key]
                self._save_database()
                return True
            return False

    def exists(self, key: str) -> bool:
        with self.lock:
            entry = self.index.get(key)
            if not entry:
                return False
            if entry.is_expired():
                del self.index[key]
                self._save_database()
                return False
            return True

    def get_all_keys(self) -> List[str]:
        with self.lock:
            self.cleanup_expired()
            return list(self.index.keys())

    def get_entry(self, key: str) -> Optional[KeyValueEntry]:
        with self.lock:
            entry = self.index.get(key)
            if entry and not entry.is_expired():
                return entry
            return None

    def get_stats(self):
        with self.lock:
            self.cleanup_expired()

            size = os.path.getsize(self.db_file) if os.path.exists(self.db_file) else 0
            accesses = sum(e.access_count for e in self.index.values())

            return {
                "total_keys": len(self.index),
                "total_accesses": accesses,
                "storage_size_mb": round(size / (1024 * 1024), 3)
            }

    def clear_all(self):
        with self.lock:
            count = len(self.index)
            self.index.clear()
            self._save_database()
            return count
