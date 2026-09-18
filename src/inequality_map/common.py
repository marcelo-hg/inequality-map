from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stable_id(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def code_version(root):
    try:
        commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    files = sorted((Path(root) / "src").rglob("*.py")) + sorted((Path(root) / "src").rglob("*.sql"))
    return {"git_commit": commit, "source_sha256": stable_id(*[(str(f.relative_to(root)), digest_file(f)) for f in files])}
