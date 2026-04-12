"""Anonymization service for PII detection and redaction."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import structlog

from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class AnonymizationService:
    """Service for detecting and anonymizing PII in fragments."""

    def __init__(self):
        settings = get_settings()
        self.enabled = getattr(settings, 'anonymization_enabled', False)
        
        if self.enabled:
            patterns = getattr(settings, 'anonymization_patterns', [])
            self._patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
            self._replacement = getattr(settings, 'anonymization_replacement', '[REDACTED]')
            
            self._field_mappings: dict[str, dict[str, str]] = {}
        else:
            self._patterns = []
            self._replacement = "[REDACTED]"
            self._field_mappings = {}

    def anonymize_text(self, text: str) -> str:
        """Anonymize PII in text."""
        if not self.enabled or not text:
            return text
        
        result = text
        for pattern in self._patterns:
            result = pattern.sub(self._replacement, result)
        
        return result

    def anonymize_dict(self, data: dict, fields: list[str] | None = None) -> dict:
        """Anonymize specific fields in a dictionary."""
        if not self.enabled:
            return data
        
        import copy
        result = copy.deepcopy(data)
        
        fields_to_anonymize = fields or self._get_default_fields()
        
        for field in fields_to_anonymize:
            if field in result and result[field] is not None:
                if isinstance(result[field], str):
                    result[field] = self.anonymize_text(result[field])
                elif isinstance(result[field], dict):
                    result[field] = self.anonymize_dict(result[field])
                elif isinstance(result[field], list):
                    result[field] = [
                        self.anonymize_text(item) if isinstance(item, str) else item
                        for item in result[field]
                    ]
        
        return result

    def pseudonymize(self, text: str, salt: str = "") -> str:
        """Replace PII with consistent pseudonyms."""
        if not self.enabled or not text:
            return text
        
        result = text
        for pattern in self._patterns:
            matches = pattern.findall(result)
            for match in matches:
                hash_input = f"{match}{salt}".encode()
                pseudonym = f"[{hashlib.md5(hash_input).hexdigest()[:8].upper()}]"
                result = result.replace(match, pseudonym)
        
        return result

    def pseudonymize_dict(self, data: dict, fields: list[str] | None = None) -> dict:
        """Pseudonymize specific fields in dictionary."""
        if not self.enabled:
            return data
        
        import copy
        result = copy.deepcopy(data)
        
        fields_to_pseudonymize = fields or self._get_default_fields()
        
        for field in fields_to_pseudonymize:
            if field in result and result[field] is not None:
                if isinstance(result[field], str):
                    result[field] = self.pseudonymize(result[field])
                elif isinstance(result[field], dict):
                    result[field] = self.pseudonymize_dict(result[field])
        
        return result

    def detect_pii(self, text: str) -> list[dict[str, Any]]:
        """Detect PII in text without modifying it."""
        if not text:
            return []
        
        detections = []
        for i, pattern in enumerate(self._patterns):
            matches = pattern.finditer(text)
            for match in matches:
                detections.append({
                    "type": pattern.pattern,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                })
        
        return detections

    def _get_default_fields(self) -> list[str]:
        """Get default fields to anonymize."""
        return ["prompt", "result", "context", "comment", "expected_output", "actual_output"]

    def get_pii_types_detected(self, text: str) -> list[str]:
        """Get list of PII types detected in text."""
        detections = self.detect_pii(text)
        return list(set(d["type"] for d in detections))


class Pseudonymizer:
    """Create consistent pseudonyms for entities."""

    def __init__(self, salt: str = "skill_fragment_engine"):
        self.salt = salt
        self._cache: dict[str, str] = {}

    def pseudonymize_name(self, name: str) -> str:
        """Create consistent pseudonym for a name."""
        if name in self._cache:
            return self._cache[name]
        
        hash_input = f"{name.lower()}{self.salt}".encode()
        pseudonym = f"PERSON_{hashlib_sha256(hash_input)[:12].upper()}"
        
        self._cache[name] = pseudonym
        return pseudonym

    def pseudonymize_email(self, email: str) -> str:
        """Create consistent pseudonym for an email."""
        if email in self._cache:
            return self._cache[email]
        
        hash_input = f"{email.lower()}{self.salt}".encode()
        pseudonym = f"EMAIL_{hashlib_sha256(hash_input)[:12].upper()}"
        
        self._cache[email] = pseudonym
        return pseudonym

    def pseudonymize_id(self, id_value: str) -> str:
        """Create consistent pseudonym for an ID."""
        if id_value in self._cache:
            return self._cache[id_value]
        
        hash_input = f"{id_value}{self.salt}".encode()
        pseudonym = f"ID_{hashlib_sha256(hash_input)[:12].upper()}"
        
        self._cache[id_value] = pseudonym
        return pseudonym

    def clear_cache(self) -> None:
        """Clear pseudonym cache."""
        self._cache.clear()


def hashlib_sha256(data: bytes) -> str:
    """Helper for hashlib."""
    return hashlib.sha256(data).hexdigest()


def get_anonymization_service() -> AnonymizationService:
    """Get singleton anonymization service."""
    global _anonymization_service_instance
    if _anonymization_service_instance is None:
        _anonymization_service_instance = AnonymizationService()
    return _anonymization_service_instance


def get_pseudonymizer() -> Pseudonymizer:
    """Get singleton pseudonymizer."""
    global _pseudonymizer_instance
    if _pseudonymizer_instance is None:
        _pseudonymizer_instance = Pseudonymizer()
    return _pseudonymizer_instance


_anonymization_service_instance = None
_pseudonymizer_instance = None