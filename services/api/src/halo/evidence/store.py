"""Local immutable object store. Keys cannot be overwritten with different bytes."""

from __future__ import annotations

import shutil
from pathlib import Path

from halo.util import sha256_hex


def clear_fixture_root(root: Path) -> None:
    resolved = root.resolve()
    if resolved.name != "object-store" and "pytest" not in str(resolved):
        raise ObjectStoreError("refusing to clear an object root that is not a fixture store")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


class ObjectStoreError(ValueError):
    pass


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        if key.startswith("/") or ".." in Path(key).parts:
            raise ObjectStoreError("object key is not allowed")
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise ObjectStoreError("object key escapes the store")
        return path

    def put_immutable(self, key: str, data: bytes, digest: str) -> None:
        actual = sha256_hex(data)
        if actual != digest:
            raise ObjectStoreError("sha256 does not match the bytes")
        path = self._path(key)
        if path.exists():
            existing = sha256_hex(path.read_bytes())
            if existing != digest:
                raise ObjectStoreError("immutable object already exists with different bytes")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise ObjectStoreError("object not found")
        return path.read_bytes()
