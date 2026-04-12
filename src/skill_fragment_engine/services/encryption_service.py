"""Encryption service for sensitive fragment data."""

from __future__ import annotations

import base64
import hashlib
import os
import structlog
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class EncryptionService:
    """Service for encrypting/decrypting sensitive fragment data."""

    def __init__(self, key: str | None = None):
        settings = get_settings()
        
        self.enabled = getattr(settings, 'encryption_enabled', False)
        
        if self.enabled:
            encryption_key = key or getattr(settings, 'encryption_key', None)
            if encryption_key:
                self._fernet = self._create_fernet(encryption_key)
            else:
                self._fernet = self._create_fernet_from_password(
                    getattr(settings, 'encryption_password', 'default_password')
                )
        else:
            self._fernet = None

    def _create_fernet(self, key: str) -> Fernet:
        """Create Fernet instance from base64 key."""
        key_bytes = base64.urlsafe_b64decode(key.encode())
        return Fernet(key_bytes)

    def _create_fernet_from_password(self, password: str) -> Fernet:
        """Create Fernet key from password using PBKDF2."""
        salt = getattr(get_settings(), 'encryption_salt', b'skill_fragment_engine_salt')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key."""
        return Fernet.generate_key().decode()

    def encrypt(self, data: str | dict | list) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt (str, dict, or list)
            
        Returns:
            Base64 encoded encrypted string
        """
        if not self.enabled or self._fernet is None:
            return str(data)
        
        import json
        data_str = json.dumps(data, sort_keys=True, default=str)
        encrypted = self._fernet.encrypt(data_str.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> Any:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Base64 encoded encrypted string
            
        Returns:
            Decrypted data (str, dict, or list)
        """
        if not self.enabled or self._fernet is None:
            return encrypted_data
        
        try:
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = self._fernet.decrypt(decoded)
            import json
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.warning("decryption_failed", error=str(e))
            return encrypted_data

    def encrypt_dict(self, data: dict, sensitive_fields: list[str] | None = None) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary to encrypt
            sensitive_fields: List of field names to encrypt (encrypts all if None)
            
        Returns:
            Dictionary with encrypted fields
        """
        if not self.enabled or self._fernet is None:
            return data
        
        import copy
        result = copy.deepcopy(data)
        
        fields_to_encrypt = sensitive_fields or self._get_default_sensitive_fields()
        
        for field in fields_to_encrypt:
            if field in result and result[field] is not None:
                if isinstance(result[field], (str, dict, list)):
                    result[field] = self.encrypt(result[field])
        
        return result

    def decrypt_dict(self, data: dict, sensitive_fields: list[str] | None = None) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary with encrypted fields
            sensitive_fields: List of field names to decrypt
            
        Returns:
            Dictionary with decrypted fields
        """
        if not self.enabled or self._fernet is None:
            return data
        
        import copy
        result = copy.deepcopy(data)
        
        fields_to_decrypt = sensitive_fields or self._get_default_sensitive_fields()
        
        for field in fields_to_decrypt:
            if field in result and result[field] is not None:
                if isinstance(result[field], str):
                    result[field] = self.decrypt(result[field])
        
        return result

    def _get_default_sensitive_fields(self) -> list[str]:
        """Get default list of sensitive fields."""
        return [
            "prompt",
            "result",
            "output",
            "expected_output",
            "actual_output",
            "comment",
            "context",
        ]


class FieldLevelEncryption:
    """Field-level encryption helper for fragments."""

    SENSITIVE_FIELDS = {
        "prompt": "Encrypt fragment prompts",
        "result": "Encrypt execution results",
        "context": "Encrypt context data",
        "output_schema": "Encrypt output schemas",
        "patterns": "Encrypt pattern content",
    }

    def __init__(self):
        settings = get_settings()
        self.enabled = getattr(settings, 'encryption_enabled', False)
        
        if self.enabled:
            sensitive_fields = getattr(settings, 'encryption_sensitive_fields', None)
            self._sensitive_fields = sensitive_fields or list(self.SENSITIVE_FIELDS.keys())
            self._encryption_service = EncryptionService()
        else:
            self._sensitive_fields = []
            self._encryption_service = None

    def encrypt_fragment(self, fragment: dict) -> dict:
        """Encrypt sensitive fields in fragment."""
        if not self.enabled or not self._encryption_service:
            return fragment
        
        import copy
        encrypted = copy.deepcopy(fragment)
        
        for field in self._sensitive_fields:
            if field in encrypted and encrypted[field] is not None:
                encrypted[field] = self._encryption_service.encrypt(encrypted[field])
        
        encrypted["_encrypted"] = True
        return encrypted

    def decrypt_fragment(self, fragment: dict) -> dict:
        """Decrypt sensitive fields in fragment."""
        if not self.enabled or not self._encryption_service:
            return fragment
        
        if not fragment.get("_encrypted", False):
            return fragment
        
        import copy
        decrypted = copy.deepcopy(fragment)
        
        for field in self._sensitive_fields:
            if field in decrypted and decrypted[field] is not None:
                decrypted[field] = self._encryption_service.decrypt(decrypted[field])
        
        decrypted.pop("_encrypted", None)
        return decrypted


def get_encryption_service() -> EncryptionService:
    """Get singleton encryption service instance."""
    global _encryption_service_instance
    if _encryption_service_instance is None:
        _encryption_service_instance = EncryptionService()
    return _encryption_service_instance


def get_field_encryption() -> FieldLevelEncryption:
    """Get singleton field-level encryption instance."""
    global _field_encryption_instance
    if _field_encryption_instance is None:
        _field_encryption_instance = FieldLevelEncryption()
    return _field_encryption_instance


_encryption_service_instance = None
_field_encryption_instance = None