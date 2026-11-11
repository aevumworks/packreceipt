"""Hash files without modifying a delivery folder; compare validated manifests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from collections import defaultdict
from datetime import datetime, timezone

from . import __version__

SCHEMA = "packreceipt.manifest.v1"
STATUSES = ("modified", "moved", "added", "removed", "unchanged")


class ReceiptError(ValueError):
    """An input cannot produce a complete, trustworthy local comparison."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_link(info: os.stat_result) -> bool:
    # Windows junctions and other reparse points must not escape the folder.
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def validate_path(path: object) -> str:
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        raise ReceiptError("Manifest paths must be nonempty relative POSIX paths.")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ReceiptError(f"Invalid manifest path: {path!r}")
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive:
        raise ReceiptError(f"Absolute manifest path is not allowed: {path!r}")
    return path


def validate_manifest(value: object) -> dict:
    """Validate at the JSON boundary; internal comparisons use this invariant."""
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ReceiptError(f"Expected manifest schema {SCHEMA}.")
    if value.get("algorithm") != "sha256":
        raise ReceiptError("Only SHA-256 manifests are supported.")
    if not isinstance(value.get("label"), str) or not value["label"].strip():
        raise ReceiptError("Manifest label must be a nonempty string.")
    files = value.get("files")
    if not isinstance(files, list):
        raise ReceiptError("Manifest files must be a list.")
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise ReceiptError("Each manifest file must be an object.")
        path = validate_path(item.get("path"))
        if path in seen:
            raise ReceiptError(f"Duplicate manifest path: {path!r}")
        seen.add(path)
        if type(item.get("size")) is not int or item["size"] < 0:
            raise ReceiptError(f"Invalid byte size for {path!r}.")
        digest = item.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ReceiptError(f"Invalid SHA-256 for {path!r}.")
    # A file cannot also be the parent of another file, regardless of host OS.
    for path in seen:
        if any(str(parent) in seen for parent in PurePosixPath(path).parents if str(parent) != "."):
            raise ReceiptError(f"Manifest contains a file/directory conflict: {path!r}")
    return value


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReceiptError(f"Cannot read manifest JSON: {path.name}: {error}") from error
    return validate_manifest(data)


def file_stamp(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def scan(root: Path, label: str | None = None) -> dict:
    """Scan a quiet folder. Reparse points/special files fail, never silently skip."""
    root = root.absolute()
    root_info = root.lstat()
    if is_link(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ReceiptError("The input must be a regular directory, not a link or junction.")
    # Reject a linked ancestor as well; the scope must be explicit on the host.
    for ancestor in root.parents:
        if is_link(ancestor.lstat()):
            raise ReceiptError("The input directory must not have a linked ancestor.")
    root = root.resolve()
    result = []
    stamps = {}
    directories = {}

    def walk(directory: Path) -> None:
        directories[directory] = file_stamp(directory.stat())
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            relative = validate_path(path.relative_to(root).as_posix())
            # DirEntry.stat() reports st_ino/st_dev as zero on Windows.
            # Path.lstat() and fstat() expose comparable file identities.
            before = path.lstat()
            if is_link(before):
                raise ReceiptError(f"Links and reparse points are not supported: {relative!r}")
            if stat.S_ISDIR(before.st_mode):
                walk(path)
                continue
            if not stat.S_ISREG(before.st_mode):
                raise ReceiptError(f"Special files are not supported: {relative!r}")
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                # On this Windows runtime lstat and fstat disagree on ctime.
                # Compare common identity/size/mtime across APIs; compare the
                # full stamp within the same API before and after reading.
                if file_stamp(before)[:4] != file_stamp(opened)[:4]:
                    raise ReceiptError(f"File changed during scan: {relative!r}")
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                after = os.fstat(stream.fileno())
            if file_stamp(opened) != file_stamp(after) or size != before.st_size:
                raise ReceiptError(f"File changed during scan: {relative!r}")
            stamps[path] = file_stamp(before)
            result.append({"path": relative, "size": size, "sha256": digest.hexdigest()})

    walk(root)
    # Re-check metadata after traversal so normal concurrent edits fail closed.
    for path, stamp in {**directories, **stamps}.items():
        if file_stamp(path.lstat()) != stamp:
            raise ReceiptError("Folder changed during scan; stop writes and scan again.")
    return {
        "schema": SCHEMA,
        "tool_version": __version__,
        "algorithm": "sha256",
        "created_at": now(),
        "label": label if label is not None else (root.name or "folder"),
        "files": sorted(result, key=lambda item: item["path"]),
    }


def compare(before: dict, after: dict, mode: str = "compare") -> dict:
    """Input manifests have been validated by load_manifest or created by scan."""
    old = {item["path"]: item for item in before["files"]}
    new = {item["path"]: item for item in after["files"]}
    rows = []
    for path in sorted(old.keys() & new.keys()):
        status = "unchanged" if (
            old[path]["sha256"] == new[path]["sha256"]
            and old[path]["size"] == new[path]["size"]
        ) else "modified"
        rows.append({"status": status, "before": old[path], "after": new[path]})
    removed = {path: old[path] for path in old.keys() - new.keys()}
    added = {path: new[path] for path in new.keys() - old.keys()}
    groups_old = defaultdict(list)
    groups_new = defaultdict(list)
    for path, item in removed.items():
        groups_old[(item["sha256"], item["size"])].append(path)
    for path, item in added.items():
        groups_new[(item["sha256"], item["size"])].append(path)
    ambiguous = []
    for digest in sorted(groups_old.keys() & groups_new.keys()):
        left, right = sorted(groups_old[digest]), sorted(groups_new[digest])
        if len(left) == len(right) == 1:
            rows.append({"status": "moved", "before": removed.pop(left[0]), "after": added.pop(right[0])})
        else:
            ambiguous.append({"sha256": digest[0], "removed": left, "added": right})
    rows.extend({"status": "removed", "before": removed[path], "after": None} for path in sorted(removed))
    rows.extend({"status": "added", "before": None, "after": added[path]} for path in sorted(added))
    rows.sort(key=lambda row: (STATUSES.index(row["status"]), (row["after"] or row["before"])["path"]))
    counts = {status: sum(row["status"] == status for row in rows) for status in STATUSES}
    return {
        "schema": "packreceipt.comparison.v1",
        "tool_version": __version__,
        "mode": mode,
        "created_at": now(),
        "before": {"label": before["label"], "file_count": len(old), "bytes": sum(x["size"] for x in old.values())},
        "after": {"label": after["label"], "file_count": len(new), "bytes": sum(x["size"] for x in new.values())},
        "matches": not any(counts[status] for status in STATUSES if status != "unchanged"),
        "counts": counts,
        "ambiguous_content_groups": ambiguous,
        "files": rows,
    }
