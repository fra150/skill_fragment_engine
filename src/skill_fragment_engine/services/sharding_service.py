from typing import Any, Dict, List, Optional
from enum import Enum
import hashlib
import threading


class ShardStrategy(Enum):
    HASH_BASED = "hash_based"
    TASK_TYPE = "task_type"
    TIME_BASED = "time_based"
    HYBRID = "hybrid"


class ShardConfig:
    def __init__(
        self,
        num_shards: int = 4,
        strategy: ShardStrategy = ShardStrategy.HASH_BASED,
        task_type_shards: Optional[Dict[str, int]] = None,
    ):
        self.num_shards = num_shards
        self.strategy = strategy
        self.task_type_shards = task_type_shards or {}


class PartitionManager:
    def __init__(self, config: ShardConfig):
        self.config = config
        self._shards: Dict[int, List[str]] = {}
        self._lock = threading.RLock()
        self._initialize_shards()

    def _initialize_shards(self):
        for i in range(self.config.num_shards):
            self._shards[i] = []

    def get_shard_id(self, fragment_id: str, task_type: str = "", created_at: Optional[str] = None) -> int:
        if self.config.strategy == ShardStrategy.TASK_TYPE:
            if task_type in self.config.task_type_shards:
                return self.config.task_type_shards[task_type]
            return hash(task_type) % self.config.num_shards
        
        elif self.config.strategy == ShardStrategy.TIME_BASED and created_at:
            try:
                import time
                from datetime import datetime
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                timestamp = dt.timestamp()
                return int(timestamp) % self.config.num_shards
            except:
                pass
        
        elif self.config.strategy == ShardStrategy.HYBRID:
            h1 = hash(fragment_id) % self.config.num_shards
            h2 = hash(task_type) % self.config.num_shards
            return (h1 + h2) % self.config.num_shards
        
        return hash(fragment_id) % self.config.num_shards

    def add_to_shard(self, shard_id: int, fragment_id: str):
        with self._lock:
            if shard_id not in self._shards:
                self._shards[shard_id] = []
            if fragment_id not in self._shards[shard_id]:
                self._shards[shard_id].append(fragment_id)

    def get_shard_fragments(self, shard_id: int) -> List[str]:
        with self._lock:
            return self._shards.get(shard_id, [])

    def get_all_shard_ids(self) -> List[int]:
        return list(self._shards.keys())

    def get_shard_stats(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return {
                shard_id: {
                    "count": len(fragments),
                    "fragment_ids": fragments[:10],
                }
                for shard_id, fragments in self._shards.items()
            }

    def remove_from_shard(self, shard_id: int, fragment_id: str):
        with self._lock:
            if shard_id in self._shards:
                self._shards[shard_id].remove(fragment_id)

    def rebalance(self, new_num_shards: int):
        with self._lock:
            old_shards = self._shards
            self.config.num_shards = new_num_shards
            self._shards = {i: [] for i in range(new_num_shards)}
            
            for old_shard_id, fragment_ids in old_shards.items():
                for frag_id in fragment_ids:
                    new_shard_id = hash(frag_id) % new_num_shards
                    self._shards[new_shard_id].append(frag_id)


_global_partition_manager: Optional[PartitionManager] = None


def get_partition_manager() -> PartitionManager:
    global _global_partition_manager
    if _global_partition_manager is None:
        config = ShardConfig(num_shards=4)
        _global_partition_manager = PartitionManager(config)
    return _global_partition_manager


def set_partition_manager(manager: PartitionManager):
    global _global_partition_manager
    _global_partition_manager = manager
