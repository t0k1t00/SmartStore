# repository.py - SmartStoreRepository with robust portalocker file locking
# Production-ready implementation: atomic writes, shared/exclusive locks,
# TTL cleanup, in-memory index + cache, background cleaner.

import os
import json
import pickle
import time
import threading
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from pathlib import Path
import tempfile

import portalocker
from fastapi import HTTPException
import redis

from .config import settings


class KeyValueEntry:
    def __init__(self, key: str, value: Any, ttl: Optional[int] = None, data_type: str = "string"):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.data_type = data_type
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.last_accessed = datetime.now()
        self.access_count = 0
        self.expires_at = (datetime.now() + timedelta(seconds=ttl)) if ttl else None

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

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
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @staticmethod
    def from_dict(d: dict) -> "KeyValueEntry":
        e = KeyValueEntry(d["key"], d["value"], d.get("ttl"), d.get("data_type", "string"))
        try:
            e.created_at = datetime.fromisoformat(d["created_at"])
            e.updated_at = datetime.fromisoformat(d["updated_at"])
            e.last_accessed = datetime.fromisoformat(d["last_accessed"])
            e.access_count = d.get("access_count", 0)
            expires = d.get("expires_at")
            e.expires_at = datetime.fromisoformat(expires) if expires else None
        except Exception:
            pass
        return e


class SmartStoreRepository:
    def __init__(self):
        self.db_file = Path(settings.SMARTSTORE_DB_FILE)
        self.lock_file = Path(settings.SMARTSTORE_DB_LOCK)
        self.timeout = getattr(settings, "FILE_LOCK_TIMEOUT", 10)

        self.index: Dict[str, dict] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        self.stats = {"hits": 0, "misses": 0, "writes": 0, "deletes": 0, "errors": 0}

        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            self.redis_available = True
        except Exception:
            self.redis_available = False
            self.redis_client = None

        os.makedirs(self.db_file.parent, exist_ok=True)

        self._initialize_db()
        self._rebuild_index_from_disk()

        self._stop_cleanup = threading.Event()
        t = threading.Thread(target=self._background_cleanup_loop, daemon=True)
        t.start()

    def _read_file_unsafe(self) -> Dict[str, dict]:
        if not self.db_file.exists():
            return {}
        try:
            with open(self.db_file, "rb") as f:
                return pickle.load(f)
        except (EOFError, pickle.UnpicklingError):
            return {}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database read error: {e}")

    def _write_file_unsafe(self, data: Dict[str, dict]):
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(self.db_file.parent))
        os.close(tmp_fd)
        try:
            with open(tmp_path, "wb") as f:
                pickle.dump(data, f)
            os.replace(tmp_path, str(self.db_file))
        except Exception as e:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Database write error: {e}")

    def _initialize_db(self):
        if not self.db_file.exists():
            try:
                with portalocker.Lock(str(self.lock_file), "w+", timeout=self.timeout, flags=portalocker.LOCK_EX):
                    if not self.db_file.exists():
                        with open(self.db_file, "wb") as f:
                            pickle.dump({}, f)
            except Exception as e:
                self.stats["errors"] += 1
                print(f"[SmartStoreRepository] Failed to initialize DB: {e}")

    def _rebuild_index_from_disk(self):
        try:
            with portalocker.Lock(str(self.lock_file), "r", timeout=self.timeout, flags=portalocker.LOCK_SH):
                data = self._read_file_unsafe()
                self.index = {}
                for k, v in data.items():
                    self.index[k] = {
                        "ttl": v.get("ttl"),
                        "expires_at": v.get("expires_at"),
                        "data_type": v.get("data_type"),
                    }
        except Exception as e:
            self.stats["errors"] += 1
            print(f"[SmartStoreRepository] Failed to rebuild index: {e}")

    def _publish_event(self, event_type: str, payload: dict):
        if not self.redis_available or not self.redis_client:
            return
        try:
            event = {"type": event_type, "timestamp": datetime.now().isoformat(), **payload}
            self.redis_client.publish("smartstore-metrics", json.dumps(event))
        except Exception:
            pass

    def cleanup_expired(self) -> List[str]:
        removed = []
        try:
            with portalocker.Lock(str(self.lock_file), "w+", timeout=self.timeout, flags=portalocker.LOCK_EX):
                data = self._read_file_unsafe()
                changed = False
                for key, entry in list(data.items()):
                    expires_at = entry.get("expires_at")
                    if expires_at:
                        try:
                            if datetime.fromisoformat(expires_at) < datetime.now():
                                del data[key]
                                changed = True
                                removed.append(key)
                                if key in self.index:
                                    del self.index[key]
                                with self._cache_lock:
                                    self._cache.pop(key, None)
                        except Exception:
                            continue
                if changed:
                    self._write_file_unsafe(data)
        except portalocker.LockException:
            pass
        except Exception as e:
            self.stats["errors"] += 1
            print(f"[SmartStoreRepository] cleanup_expired error: {e}")
        return removed

    def _background_cleanup_loop(self):
        interval = max(5, int(getattr(settings, "CLEANUP_INTERVAL", 10)))
        while not self._stop_cleanup.is_set():
            try:
                self.cleanup_expired()
            except Exception:
                pass
            time.sleep(interval)

    def get(self, key: str) -> Optional[Any]:
        start = time.time()
        try:
            with self._cache_lock:
                if key in self._cache:
                    self.stats["hits"] += 1
                    self._publish_event("cache_hit", {"key": key, "latency_ms": (time.time() - start) * 1000})
                    return self._cache[key]

            try:
                self.cleanup_expired()
            except Exception:
                pass

            with portalocker.Lock(str(self.lock_file), "r", timeout=self.timeout, flags=portalocker.LOCK_SH):
                data = self._read_file_unsafe()
                if key not in data:
                    self.stats["misses"] += 1
                    self._publish_event("get_miss", {"key": key})
                    return None

                entry_data = data[key]
                expires = entry_data.get("expires_at")
                if expires:
                    try:
                        if datetime.fromisoformat(expires) < datetime.now():
                            self.stats["misses"] += 1
                            return None
                    except Exception:
                        pass

                self.stats["hits"] += 1
                value = entry_data.get("value")
                with self._cache_lock:
                    if len(self._cache) < getattr(settings, "CACHE_SIZE", 10000):
                        self._cache[key] = value

                self._publish_event("get_success", {"key": key, "latency_ms": (time.time() - start) * 1000})
                return value

        except portalocker.LockException:
            self.stats["errors"] += 1
            raise HTTPException(status_code=503, detail="Database is busy")
        except HTTPException:
            raise
        except Exception as e:
            self.stats["errors"] += 1
            raise HTTPException(status_code=500, detail=f"Failed to get key: {e}")

    def put(self, key: str, value: Any, ttl: Optional[int] = None, data_type: str = "string") -> bool:
        start = time.time()
        try:
            with portalocker.Lock(str(self.lock_file), "w+", timeout=self.timeout, flags=portalocker.LOCK_EX):
                data = self._read_file_unsafe()
                entry = KeyValueEntry(key, value, ttl, data_type)
                entry.updated_at = datetime.now()
                data[key] = entry.to_dict()
                self._write_file_unsafe(data)

                self.index[key] = {
                    "ttl": ttl,
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                    "data_type": data_type,
                }
                with self._cache_lock:
                    self._cache[key] = value

                self.stats["writes"] += 1
                self._publish_event("put_success", {"key": key, "latency_ms": (time.time() - start) * 1000})
                return True

        except portalocker.LockException:
            self.stats["errors"] += 1
            raise HTTPException(status_code=503, detail="Database is busy")
        except Exception as e:
            self.stats["errors"] += 1
            raise HTTPException(status_code=500, detail=f"Failed to put key: {e}")

    def delete(self, key: str) -> bool:
        try:
            with portalocker.Lock(str(self.lock_file), "w+", timeout=self.timeout, flags=portalocker.LOCK_EX):
                data = self._read_file_unsafe()
                if key not in data:
                    return False
                del data[key]
                self._write_file_unsafe(data)

                if key in self.index:
                    del self.index[key]
                with self._cache_lock:
                    self._cache.pop(key, None)

                self.stats["deletes"] += 1
                self._publish_event("delete_success", {"key": key})
                return True
        except portalocker.LockException:
            self.stats["errors"] += 1
            raise HTTPException(status_code=503, detail="Database is busy")
        except Exception as e:
            self.stats["errors"] += 1
            raise HTTPException(status_code=500, detail=f"Failed to delete key: {e}")

    def get_all_keys(self) -> List[str]:
        try:
            try:
                self.cleanup_expired()
            except Exception:
                pass

            with portalocker.Lock(str(self.lock_file), "r", timeout=self.timeout, flags=portalocker.LOCK_SH):
                data = self._read_file_unsafe()
                valid_keys = []
                for k, v in data.items():
                    expires_at = v.get("expires_at")
                    if expires_at:
                        try:
                            if datetime.fromisoformat(expires_at) < datetime.now():
                                continue
                        except Exception:
                            pass
                    valid_keys.append(k)
                return valid_keys
        except portalocker.LockException:
            raise HTTPException(status_code=503, detail="Database is busy")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def get_stats(self) -> dict:
        try:
            with portalocker.Lock(str(self.lock_file), "r", timeout=self.timeout, flags=portalocker.LOCK_SH):
                data = self._read_file_unsafe()
                total_keys = len(data)
                hit_rate = (
                    (self.stats["hits"] / (self.stats["hits"] + self.stats["misses"]) * 100)
                    if (self.stats["hits"] + self.stats["misses"]) > 0
                    else 0
                )
                storage_size = 0
                try:
                    storage_size = os.path.getsize(self.db_file) if self.db_file.exists() else 0
                except Exception:
                    storage_size = 0

                return {
                    "total_keys": total_keys,
                    "cache_size": len(self._cache),
                    "hits": self.stats["hits"],
                    "misses": self.stats["misses"],
                    "hit_rate": round(hit_rate, 2),
                    "writes": self.stats["writes"],
                    "deletes": self.stats["deletes"],
                    "errors": self.stats["errors"],
                    "storage_size_bytes": storage_size,
                }
        except portalocker.LockException:
            raise HTTPException(status_code=503, detail="Database is busy")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def shutdown(self):
        self._stop_cleanup.set()


# Singleton instance
repository = SmartStoreRepository()
