# Security & Privacy - Skill Fragment Engine

## Overview

This document describes the security and privacy features implemented in SFE.

## Implemented Features

### 1. Encryption (COMPLETED)

Field-level encryption for sensitive fragment data using Fernet (AES-128 + HMAC).

**Features:**
- Key derivation with PBKDF2 (100,000 iterations)
- Field-level encryption (prompt, result, context)
- Transparent encrypt/decrypt in FragmentStore

**Configuration:**
```env
ENCRYPTION_ENABLED=true
ENCRYPTION_KEY=your_base64_key
# or
ENCRYPTION_PASSWORD=your_password
```

See `docs/ENCRYPTION.md` for full documentation.

---

### 2. RBAC (Role-Based Access Control) (COMPLETED)

Role-based access control for API endpoints.

**Roles:**
| Role | Permissions |
|------|-------------|
| ADMIN | Full access to all operations |
| POWER_USER | Fragment read/write, execution, feedback, clustering, metrics |
| USER | Fragment read/search, execute, feedback |
| READONLY | Read-only access to fragments, metrics |
| GUEST | Basic read access |

**Permissions:**
- `fragment:read`, `fragment:write`, `fragment:delete`, `fragment:search`
- `execute:read`, `execute:write`
- `feedback:read`, `feedback:write`
- `version:read`, `version:write`, `version:rollback`
- `clustering:read`, `clustering:write`
- `admin:read`, `admin:write`, `admin:metrics`, `admin:prune`, `admin:decay`

**Usage:**
```python
from skill_fragment_engine.services.rbac_service import RBACService, Role, Permission

rbac = RBACService()
rbac.register_user("user123", Role.USER)
rbac.has_permission("user123", Permission.FRAGMENT_READ)
```

**Configuration:**
```env
RBAC_ENABLED=true
RBAC_DEFAULT_ROLE=user
```

---

### 3. Audit Logging (COMPLETED)

Comprehensive audit logging for all operations.

**Tracked Actions:**
- Fragment: create, read, update, delete, search
- Execution: reuse, adapt, recompute
- Feedback: create, read
- Versioning: create, rollback, read
- Clustering: run, read
- Admin: prune, decay, metrics
- Auth: login, logout, denied

**Storage:**
- JSON file at `./data/audit.json`
- Configurable max events (default: 10,000)
- Queryable by user, action, resource, time range

**Usage:**
```python
from skill_fragment_engine.services.audit_service import AuditService, AuditAction

audit = AuditService()
audit.log(
    action=AuditAction.FRAGMENT_CREATE,
    user_id="user123",
    resource_type="fragment",
    resource_id="frag-456",
    details={"task_type": "code_generation"}
)

events = audit.get_events(user_id="user123", limit=50)
stats = audit.get_stats()
```

**Configuration:**
```env
AUDIT_ENABLED=true
AUDIT_LOG_PATH=./data/audit.json
AUDIT_MAX_EVENTS=10000
```

---

### 4. Anonymization (COMPLETED)

PII detection and redaction/anonymization.

**Detection Patterns:**
- ID numbers (2 letters + 6-9 digits)
- SSN (XXX-XX-XXXX)
- Credit cards (16 digits)
- Emails

**Features:**
- `anonymize_text()` - Replace PII with `[REDACTED]`
- `pseudonymize()` - Replace with consistent pseudonyms
- `detect_pii()` - Detect without modifying

**Usage:**
```python
from skill_fragment_engine.services.anonymization_service import AnonymizationService

anon = AnonymizationService()

# Anonymize
result = anon.anonymize_text("Contact john@example.com for details")
# Output: "Contact [REDACTED] for details"

# Pseudonymize (consistent)
result = anon.pseudonymize("john@example.com")
# Output: "EMAIL_A1B2C3D4E5F6"

# Detect PII
detections = anon.detect_pii("SSN: 123-45-6789")
# Output: [{"type": "...", "value": "123-45-6789", "start": 5, "end": 15}]
```

**Configuration:**
```env
ANONYMIZATION_ENABLED=true
ANONYMIZATION_REPLACEMENT=[REDACTED]
```

---

## Configuration Summary

```env
# Security
ENCRYPTION_ENABLED=false
ENCRYPTION_KEY=
ENCRYPTION_PASSWORD=default_password

RBAC_ENABLED=false
RBAC_DEFAULT_ROLE=user

AUDIT_ENABLED=true
AUDIT_LOG_PATH=./data/audit.json
AUDIT_MAX_EVENTS=10000

ANONYMIZATION_ENABLED=false
ANONYMIZATION_REPLACEMENT=[REDACTED]
```

## Upcoming Features

- IP-based rate limiting
- API key authentication
- Session management
- Granular resource-level permissions