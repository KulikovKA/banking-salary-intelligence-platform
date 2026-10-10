import io
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.ingestion.adapters import discover_documents
from app.ingestion.errors import IngestionError
from app.storage.local import LocalBlobStore


def test_atomic_archive_dedup_and_corpus_isolation(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    payload = b"%PDF-1.7 synthetic\n%%EOF"
    with ThreadPoolExecutor(max_workers=4) as executor:
        receipts = list(executor.map(lambda _: store.put([payload], "pdf", "synthetic"), range(8)))
    assert len({r.storage_key for r in receipts}) == 1
    assert store.verify(receipts[0]).read_bytes() == payload
    other = store.put([payload], "pdf", "real")
    assert other.sha256 == receipts[0].sha256 and other.storage_key != receipts[0].storage_key
    assert not list(tmp_path.rglob(".pending-*"))
    assert len(store.reconcile({receipts[0].storage_key})["orphan"]) == 1


def test_failed_atomic_write_and_corruption(tmp_path: Path, monkeypatch) -> None:
    store = LocalBlobStore(tmp_path)

    def fail(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(os, "link", fail)
    with pytest.raises(IngestionError, match="STORAGE_WRITE_FAILED"):
        store.put([b"%PDF-1.7 synthetic"], "pdf", "synthetic")
    assert not list(tmp_path.rglob(".pending-*"))
    assert not store.reconcile(set())["orphan"]
    monkeypatch.undo()
    receipt = store.put([b"%PDF-1.7 synthetic"], "pdf", "synthetic")
    store.path(receipt.storage_key).write_bytes(b"corrupt")
    with pytest.raises(IngestionError, match="STORAGE_HASH_MISMATCH"):
        store.verify(receipt)
    with pytest.raises(IngestionError, match="STORAGE_HASH_MISMATCH"):
        store.put([b"%PDF-1.7 synthetic"], "pdf", "synthetic")


@pytest.mark.parametrize("key", ["../outside", "real/aa/../outside", "C:/outside", "anything"])
def test_invalid_storage_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(IngestionError, match="STORAGE_PATH_INVALID"):
        LocalBlobStore(tmp_path).path(key)


def test_storage_size_limit_and_invalid_format(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, max_bytes=16)
    with pytest.raises(IngestionError, match="SIZE_LIMIT"):
        store.put([b"%PDF-" + b"x" * 50], "pdf", "synthetic")
    with pytest.raises(IngestionError, match="FORMAT_INVALID"):
        store.put([b"not pdf"], "pdf", "synthetic")
    assert not store.reconcile(set())["orphan"]


def workbook(extra_name: str | None = None, extra_content: bytes = b"") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        if extra_name:
            archive.writestr(extra_name, extra_content)
    return stream.getvalue()


@pytest.mark.parametrize(
    "name,content",
    [
        ("xl/vbaProject.bin", b"macro"),
        ("xl/externalLinks/link.xml", b"external"),
        ("../outside", b"bad"),
        ("xl/_rels/workbook.xml.rels", b'<Relationship TargetMode="External"/>'),
    ],
)
def test_xlsx_unsafe_features_rejected(tmp_path: Path, name: str, content: bytes) -> None:
    store = LocalBlobStore(tmp_path)
    with pytest.raises(IngestionError, match="FORMAT_INVALID"):
        store.put([workbook(name, content)], "xlsx", "synthetic")


def test_xlsx_can_be_archived_without_external_execution(tmp_path: Path) -> None:
    receipt = LocalBlobStore(tmp_path).put([workbook()], "xlsx", "synthetic")
    assert receipt.media_type.endswith("spreadsheetml.sheet")


@pytest.mark.parametrize("bank", ["kuban_credit", "vtb"])
def test_discovery_preserves_section_dates_and_pending(bank) -> None:
    html = """<html><section class="archive"><a href="/old.pdf">Old 01.01.2024</a></section>
      <section class="current"><a href="/new.xlsx">New 05.10.2026</a></section>
      <a href="/unknown.pdf">Unknown date</a><a href="javascript:alert(1)">Ignored</a></html>"""
    candidates = discover_documents(bank, "https://example.com/index/", html)
    assert [(c.kind, c.section, c.decision) for c in candidates] == [
        ("pdf", "archive", "pending"),
        ("xlsx", "current", "pending"),
        ("pdf", "unknown", "pending"),
    ]
    assert candidates[1].effective_date_candidate.isoformat() == "2026-10-05"
    assert candidates[2].effective_date_candidate is None
