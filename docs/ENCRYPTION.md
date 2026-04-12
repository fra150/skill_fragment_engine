# Encryption - Skill Fragment Engine

## Overview

The encryption module provides field-level encryption for sensitive fragment data stored on disk. This ensures that even if the storage is compromised, sensitive information remains protected.

## Features

- **Fernet Symmetric Encryption**: AES-128 encryption with HMAC for integrity
- **Key Derivation**: PBKDF2 key derivation from password (100,000 iterations)
- **Field-Level Encryption**: Encrypt only sensitive fields, keep searchable fields readable
- **Transparent Encryption/Decryption**: Automatic encryption on save, decryption on load

## Configuration

In `.env` file:

```env
# Enable encryption
ENCRYPTION_ENABLED=true

# Option 1: Provide your own Fernet key (base64 encoded)
ENCRYPTION_KEY=your_base64_encoded_key

# Option 2: Use password-based key derivation
ENCRYPTION_PASSWORD=your_secure_password

# Salt for key derivation (should be unique per deployment)
ENCRYPTION_SALT=your_unique_salt_bytes

# Fields to encrypt (default: ["prompt", "result", "context"])
ENCRYPTION_SENSITIVE_FIELDS=["prompt", "result", "context", "expected_output"]
```

In `config.py`:

```python
# Encryption settings
encryption_enabled: bool = False
encryption_key: str | None = None
encryption_password: str = "default_password"
encryption_salt: bytes = b'skill_fragment_engine_salt'
encryption_sensitive_fields: list[str] = ["prompt", "result", "context"]
```

## Generating Keys

### Generate a new encryption key:

```python
from skill_fragment_engine.services.encryption_service import EncryptionService

key = EncryptionService.generate_key()
print(f"Use this key: {key}")
```

Output example:
```
Use this key: abc123xyz...base64encodedkey...
```

## Usage

### Python API

```python
from skill_fragment_engine.services.encryption_service import EncryptionService

# Create service (reads from settings)
encryption = EncryptionService()

# Encrypt data
encrypted = encryption.encrypt({"prompt": "secret data", "result": "output"})
print(encrypted)  # Base64 encoded string

# Decrypt data
decrypted = encryption.decrypt(encrypted)
print(decrypted)  # Original dict
```

### Field-Level Encryption

```python
from skill_fragment_engine.services.encryption_service import FieldLevelEncryption

field_enc = FieldLevelEncryption()

# Encrypt fragment
fragment = {"prompt": "...", "result": "...", "task_type": "code_generation"}
encrypted = field_enc.encrypt_fragment(fragment)

# Decrypt fragment
decrypted = field_enc.decrypt_fragment(encrypted)
```

### Fragment Store Integration

The `FragmentStore` automatically handles encryption:

```python
from skill_fragment_engine.store import FragmentStore

store = FragmentStore()

# Save fragment - automatically encrypted if ENCRYPTION_ENABLED=true
store.save_fragment(fragment, prompt, context)

# Load fragment - automatically decrypted
fragment = store.get_fragment(fragment_id)
```

## Security Considerations

1. **Key Management**: Store encryption keys securely (environment variables, secrets manager)
2. **Salt**: Use unique salt per deployment
3. **Iterations**: PBKDF2 uses 100,000 iterations (adjustable)
4. **Algorithm**: Uses Fernet (AES-128-CBC + HMAC-SHA256)

## Storage Format

Encrypted fragments on disk:

```json
{
  "fragment_id": "...",
  "task_type": "code_generation",
  "prompt": "gAAAAABk...",  // Encrypted
  "fragment": {...},
  "_encrypted": true
}
```

The `_encrypted` flag indicates the fragment was encrypted. The store will auto-decrypt when loading.

## Disable Encryption

Set in `.env`:

```env
ENCRYPTION_ENABLED=false
```

Existing encrypted fragments will still be decrypted correctly if the key is available.