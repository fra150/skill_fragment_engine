"""Fragment storage and lookup."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.models import SkillFragment
from skill_fragment_engine.retrieval.hasher import InputHasher
from skill_fragment_engine.retrieval.similarity import SimilarityFactory
from skill_fragment_engine.services.encryption_service import get_field_encryption


@dataclass(frozen=True)
class StoredFragment:
    fragment: SkillFragment
    prompt: str
    input_hash: str


class FragmentStore:
    def __init__(self, path: str | None = None):
        settings = get_settings()
        self.path = path or settings.fragment_store_path
        self._data: dict[str, dict[str, Any]] = {}
        self._hasher = InputHasher()
        self._similarity_algorithm = SimilarityFactory.create(
            getattr(settings, 'similarity_algorithm', 'jaccard')
        )
        self._encryption = get_field_encryption()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            self._data = {}
            return

        with open(self.path, encoding="utf-8") as f:
            raw = json.load(f)
            self._data = raw if isinstance(raw, dict) else {}
        
        self._decrypt_fragments()

    def _decrypt_fragments(self) -> None:
        """Decrypt fragments if encryption is enabled."""
        for fragment_id, rec in self._data.items():
            if rec.get("_encrypted", False):
                decrypted = self._encryption.decrypt_fragment(rec)
                self._data[fragment_id] = decrypted

    def _save(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        data_to_save = self._encrypt_fragments_before_save()
        
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)

    def _encrypt_fragments_before_save(self) -> dict[str, Any]:
        """Encrypt fragments before saving to disk."""
        if not self._encryption.enabled:
            return self._data
        
        encrypted_data = {}
        for fragment_id, rec in self._data.items():
            encrypted_data[fragment_id] = self._encryption.encrypt_fragment(rec)
        return encrypted_data

    def _compute_input_hash(
        self,
        task_type: str,
        prompt: str,
        context: dict[str, Any] | None,
        parameters: dict[str, Any] | None,
    ) -> str:
        combined = self._hasher.hash_input(prompt, context, parameters)
        normalized = f"{task_type}::{combined}"
        return self._hasher.hash_prompt(normalized)

    def save_fragment(
        self,
        fragment: SkillFragment,
        prompt: str,
        context: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        fragment_id = str(fragment.fragment_id)
        task_type = fragment.task_type.value if hasattr(fragment.task_type, "value") else str(fragment.task_type)
        input_hash = self._compute_input_hash(task_type, prompt, context, parameters)

        self._data[fragment_id] = {
            "task_type": task_type,
            "prompt": prompt,
            "input_hash": input_hash,
            "fragment": fragment.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._save()

    def update_fragment(self, fragment: SkillFragment) -> None:
        fragment_id = str(fragment.fragment_id)
        rec = self._data.get(fragment_id)
        if rec is None:
            return

        rec["fragment"] = fragment.model_dump(mode="json")
        rec["updated_at"] = datetime.utcnow().isoformat()
        self._data[fragment_id] = rec
        self._save()

    def get_fragment(self, fragment_id: str | UUID) -> SkillFragment | None:
        key = str(fragment_id)
        rec = self._data.get(key)
        if not rec:
            return None
        frag_raw = rec.get("fragment")
        if not isinstance(frag_raw, dict):
            return None
        return SkillFragment.model_validate(frag_raw)

    def get_prompt(self, fragment_id: str | UUID) -> str | None:
        key = str(fragment_id)
        rec = self._data.get(key)
        if not rec:
            return None
        prompt = rec.get("prompt")
        return str(prompt) if prompt is not None else None

    def lookup_exact(
        self,
        task_type: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> StoredFragment | None:
        target_hash = self._compute_input_hash(task_type, prompt, context, parameters)

        for fragment_id, rec in self._data.items():
            if rec.get("task_type") != task_type:
                continue
            if rec.get("input_hash") != target_hash:
                continue
            frag_raw = rec.get("fragment")
            if not isinstance(frag_raw, dict):
                continue
            fragment = SkillFragment.model_validate(frag_raw)
            stored_prompt = rec.get("prompt") or ""
            return StoredFragment(
                fragment=fragment,
                prompt=stored_prompt,
                input_hash=target_hash,
            )

        return None

    def lookup_similar(
        self,
        task_type: str,
        prompt: str,
        top_k: int = 3,
        min_overlap: float | None = None,
    ) -> list[tuple[str, float]]:
        settings = get_settings()
        threshold = settings.keyword_similarity_min_overlap if min_overlap is None else min_overlap

        query_words = {w for w in prompt.lower().split() if w}
        if not query_words:
            return []

        scored: list[tuple[str, float]] = []
        for fragment_id, rec in self._data.items():
            if rec.get("task_type") != task_type:
                continue
            stored_prompt = str(rec.get("prompt") or "")
            stored_words = {w for w in stored_prompt.lower().split() if w}
            overlap = self._similarity_algorithm.compute_similarity(query_words, stored_words)
            if overlap >= threshold:
                scored.append((fragment_id, round(float(overlap), 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._data)
