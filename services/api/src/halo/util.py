from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

FIXTURE_NS = uuid.UUID("8c1c6b2e-7a4d-4f0a-9b1e-2d5a6c7e8f90")


def fid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(FIXTURE_NS, "/".join(parts))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"cannot canonicalize {type(value).__name__}")


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_json_default).encode()


def canonical_sha256(data: Any) -> str:
    return sha256_hex(canonical_json(data))
