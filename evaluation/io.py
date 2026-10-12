"""Byte-pinned artifacts and secret-safe errors."""

import hashlib
import json
from pathlib import Path

from evaluation.schema import Gold, Observations


def load_gold(path: Path, expected_sha256: str) -> tuple[Gold, str]:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError("GOLD_HASH_MISMATCH")
    return Gold.model_validate_json(raw), actual


def load_observations(path: Path) -> Observations:
    return Observations.model_validate_json(path.read_bytes())


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
