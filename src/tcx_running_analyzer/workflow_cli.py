"""Local agent-friendly TCX archive ingestion and repeatable history rebuild.

Command examples:
  python -m tcx_running_analyzer.workflow_cli ingest --workspace local-data --tz-offset +04:00 file.tcx
  python -m tcx_running_analyzer.workflow_cli rebuild --workspace local-data

The user-metadata JSON is never generated from TCX and is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .cli import find_files, main as analyzer_main
from .core import parse_tz


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ingest(paths: list[str], tcx_dir: Path, recursive: bool = True) -> tuple[int, int]:
    """Copy only new files; reject all filename conflicts before copying anything."""
    sources = find_files(paths, recursive=recursive)
    if not sources:
        raise ValueError("no TCX inputs found")
    tcx_dir.mkdir(parents=True, exist_ok=True)
    known = {p.name.casefold(): p for p in tcx_dir.iterdir() if p.is_file()}
    planned: dict[str, tuple[Path, str]] = {}
    known_hashes = {file_sha(p) for p in known.values()}
    planned_hashes: set[str] = set()
    added = skipped = 0
    for source in sources:
        key = source.name.casefold()
        checksum = file_sha(source)
        if key in known:
            if file_sha(known[key]) != checksum:
                raise ValueError(f"filename conflict: {source.name}; existing TCX has different bytes")
            skipped += 1
            continue
        if key in planned:
            if planned[key][1] != checksum:
                raise ValueError(f"filename conflict within new inputs: {source.name}")
            skipped += 1
            continue
        # A byte-identical file with a different name is the same workout export.
        if checksum in known_hashes or checksum in planned_hashes:
            skipped += 1
            continue
        planned[key] = (source, checksum)
        planned_hashes.add(checksum)
    for source, checksum in planned.values():
        destination = tcx_dir / source.name
        # Files are user-owned input. Do not overwrite, including on races.
        try:
            with destination.open("xb") as output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
            if file_sha(destination) != checksum:
                destination.unlink(missing_ok=True)
                raise OSError(f"copy verification failed: {source}")
        except FileExistsError as exc:
            raise ValueError(f"concurrent filename conflict: {destination.name}") from exc
        added += 1
    return added, skipped


def run_analyzer(tcx_dir: Path, dest: Path, tz_offset: str, metadata: Path | None = None) -> Path:
    with tempfile.NamedTemporaryFile(prefix=".running-report-", suffix=".json", dir=dest.parent, delete=False) as f:
        temporary = Path(f.name)
    temporary.unlink()
    try:
        argv = [str(tcx_dir), "--recursive", "--tz-offset", tz_offset, "--output", str(temporary)]
        if metadata is not None:
            argv += ["--metadata", str(metadata)]
        code = analyzer_main(argv)
        if code != 0:
            raise ValueError(f"analyzer failed with exit code {code}; existing report remains unchanged")
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def rebuild(workspace: Path, tz_offset: str) -> None:
    root = workspace.resolve()
    tcx_dir = root / "tcx"
    if not tcx_dir.is_dir():
        raise ValueError(f"missing TCX directory: {tcx_dir}")
    raw = root / "running-activities.json"
    combined = root / "running-history.json"
    meta = root / "running-metadata.json"
    first = second = None
    try:
        first = run_analyzer(tcx_dir, raw, tz_offset)
        second = run_analyzer(tcx_dir, combined, tz_offset, meta if meta.exists() else None)
        # Publish only after both analyses succeeded; no half-written JSON.
        os.replace(first, raw)
        os.replace(second, combined)
    finally:
        if first is not None: first.unlink(missing_ok=True)
        if second is not None: second.unlink(missing_ok=True)
    print(f"Raw report: {raw}\nEnriched history: {combined}\nUser metadata (unchanged): {meta}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Locally ingest TCX and rebuild persistent training history")
    cmds = parser.add_subparsers(dest="command", required=True)
    add = cmds.add_parser("ingest", help="add TCX without overwriting existing files; rebuild reports")
    add.add_argument("--workspace", type=Path, required=True)
    add.add_argument("--tz-offset", default=None, help="set once when workspace is created, e.g. +04:00")
    add.add_argument("--no-recursive", action="store_true")
    add.add_argument("inputs", nargs="+", help="new TCX files or folders")
    refresh = cmds.add_parser("rebuild", help="regenerate raw and enriched reports after metadata changed")
    refresh.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace.expanduser().resolve()
        settings = workspace / "workflow-settings.json"
        saved = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else None
        if saved is not None and (not isinstance(saved, dict) or not isinstance(saved.get("tz_offset"), str)):
            raise ValueError("invalid workflow-settings.json")
        if args.command == "ingest":
            offset = args.tz_offset or (saved["tz_offset"] if saved else "+00:00")
            parse_tz(offset)
            if saved and args.tz_offset is not None and offset != saved["tz_offset"]:
                raise ValueError("timezone differs from saved workspace settings; adjust settings explicitly")
            added, skipped = ingest(args.inputs, workspace / "tcx", recursive=not args.no_recursive)
            rebuild(workspace, offset)
            if saved is None:
                settings.write_text(json.dumps({"tz_offset": offset}, indent=2) + "\n", encoding="utf-8")
            print(f"TCX ingested: {added} new, {skipped} already present")
        else:
            if saved is None:
                raise ValueError("workspace has no workflow-settings.json; ingest TCX first")
            parse_tz(saved["tz_offset"])
            rebuild(workspace, saved["tz_offset"])
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
