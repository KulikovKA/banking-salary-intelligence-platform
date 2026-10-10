"""Immutable namespace-separated files; a DB failure leaves a safe orphan.

Publish uses an atomic hard link (no clobber), then removes the private temp.
Storage root must be owned exclusively by the service account. Reconciliation
is read-only; never remove a blob simply because one transaction rolled back.
"""

import hashlib
import os
import re
import stat
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.ingestion.errors import IngestionError
from app.ingestion.formats import DocumentKind, check_format

CorpusKind = Literal["synthetic", "real"]


@dataclass(frozen=True)
class BlobReceipt:
    sha256: str
    byte_size: int
    media_type: str
    storage_key: str
    corpus_kind: CorpusKind


class LocalBlobStore:
    def __init__(self, root: Path, max_bytes: int = 50 * 1024 * 1024) -> None:
        if root.is_symlink():
            raise IngestionError("STORAGE_PATH_INVALID")
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"(?:real|synthetic)/[a-f0-9]{2}/[a-f0-9]{64}", key):
            raise IngestionError("STORAGE_PATH_INVALID")
        path = self.root / key
        for item in (path, *path.parents):
            if item == self.root:
                break
            if item.is_symlink() or (
                item.exists()
                and getattr(item.lstat(), "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ):
                raise IngestionError("STORAGE_PATH_INVALID")
        # Resolve directories, not a newly linked leaf that other writers are deduplicating.
        # Windows may resolve a hard-link leaf via its concurrently removed temporary alias.
        if not path.parent.resolve().is_relative_to(self.root):
            raise IngestionError("STORAGE_PATH_INVALID")
        return path

    def verify(self, receipt: BlobReceipt) -> Path:
        if receipt.storage_key != f"{receipt.corpus_kind}/{receipt.sha256[:2]}/{receipt.sha256}":
            raise IngestionError("STORAGE_RECEIPT_INVALID")
        path = self.path(receipt.storage_key)
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(65536):
                    digest.update(chunk)
                    size += len(chunk)
            if digest.hexdigest() != receipt.sha256 or size != receipt.byte_size:
                raise IngestionError("STORAGE_HASH_MISMATCH")
            return path
        except OSError as exc:
            raise IngestionError("STORAGE_MISSING") from exc

    def put(
        self, chunks: Iterable[bytes], kind: DocumentKind, corpus_kind: CorpusKind
    ) -> BlobReceipt:
        from app.ingestion.formats import MEDIA_TYPES

        if corpus_kind not in ("real", "synthetic"):
            raise IngestionError("CORPUS_INVALID")
        namespace = self.root / corpus_kind
        if namespace.is_symlink():
            raise IngestionError("STORAGE_PATH_INVALID")
        namespace.mkdir(exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=namespace)
        temporary = Path(name)
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, "wb") as stream:
                for chunk in chunks:
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise IngestionError("SIZE_LIMIT")
                    stream.write(chunk)
                    digest.update(chunk)
                if not size:
                    raise IngestionError("FORMAT_INVALID")
                stream.flush()
                os.fsync(stream.fileno())
            check_format(temporary, kind)
            sha = digest.hexdigest()
            key = f"{corpus_kind}/{sha[:2]}/{sha}"
            target = self.path(key)
            target.parent.mkdir(exist_ok=True)
            receipt = BlobReceipt(sha, size, MEDIA_TYPES[kind], key, corpus_kind)
            try:
                os.link(temporary, target)
            except FileExistsError:
                self.verify(receipt)
            if os.name != "nt":
                directory_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            self.verify(receipt)
            return receipt
        except OSError as exc:
            raise IngestionError("STORAGE_WRITE_FAILED") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def reconcile(self, referenced_keys: set[str]) -> dict[str, list[str]]:
        files = {
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in self.root.glob("*/*/*")
            if p.is_file()
        }
        return {
            "missing": sorted(referenced_keys - files),
            "orphan": sorted(files - referenced_keys),
        }
