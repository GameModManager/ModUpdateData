#!/usr/bin/env python3
"""ModUpdateData dataset pipeline: rebuild manifest + indexes in place.

Idempotent. Run from the repo root (or pass --data-dir). Used by CI to repair
drift (bytes/sha256 stale after manual edits) and by the scraper to refresh
manifest hashes after a push.

Pipeline:
  1. Walk every data/<lo>-<hi>.json shard. Normalize timestamps to canonical
     UTC '...Z' (the +0000/+00:00 form is rewritten in place). Rewrite file
     only if a timestamp changed. Recompute bytes + sha256 of the post-write
     content.
  2. Re-emit data/index.json (id -> updated) in id-sorted order, normalised.
  3. Group by game, emit data/index.<GAME>.json per game that has >=1 row.
     '???' is its own bucket (legacy fallback).
  4. Update data/manifest.json: generated_at, total_mods, total_shards, shard
     bytes/sha, index entry, plus additive by_game counts and per_game_index
     map. Schema_version stays at 1 (additive only).
  5. Stash current HEAD commit in manifest['commit'] for traceability.

Scraper hook: this module is importable. The scraper can do
``from regen import regen_manifest_and_index`` (or sys.path-add the tools
dir) and call it after a push instead of running its own copy. Signature
matches the scraper's existing regen_manifest_and_index(data_dir, log=print).

Returns dict with shards/mods/timestamps_fixed/per_game_indexed keys.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Callable, Dict, List, Tuple

# Canonical game order, used for by_game keys + per_game_index iteration.
# Must stay aligned with validate.py ALLOWED_GAME + SCHEMA.md.
GAME_ORDER: Tuple[str, ...] = (
    "SE", "LE", "FO4", "SF", "OB", "OBR", "S4", "S3", "???",
)

# Match ISO-8601 with any zone designator: Z, +0000, +00:00.
_TS_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:Z|[+-]\d{4}|[+-]\d{2}:\d{2})"
)


def _canon_ts(m: "re.Match[str]") -> str:
    """Rewrite a matched ISO-8601 timestamp to canonical '...Z' form.

    Accepts Z, +0000, +HHMM, +HH:MM. Returns the original match if it
    cannot be parsed (caller may flag the row as a validation error).
    """
    s = m.group(0)
    # Strip zone designator (Z or +HHMM / +HH:MM) and parse as naive UTC.
    if s.endswith("Z"):
        base = s[:-1]
    else:
        # Drop everything from the first +/- that's part of the zone (i.e.
        # the +/- immediately following the seconds field, position 19).
        base = s[:19] if len(s) > 19 else s
    try:
        dt = _dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return s
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise_timestamps_text(text: str) -> Tuple[str, int]:
    """Rewrite every ISO timestamp in ``text`` to canonical UTC '...Z'.

    Pure string surgery: key order, indentation, trailing newlines are
    untouched. Unparseable values are left as-is. Returns (new_text, n_changed).
    """
    matches = _TS_RE.findall(text)
    out = _TS_RE.sub(_canon_ts, text)
    changed = sum(1 for a, b in zip(matches, _TS_RE.findall(out)) if a != b)
    return out, changed


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_git_head(data_dir: str) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=data_dir, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _shard_paths(data_dir: str) -> List[str]:
    """All data/<lo>-<hi>.json files, sorted by range."""
    data_sub = os.path.join(data_dir, "data")
    paths = []
    for p in sorted(glob.glob(os.path.join(data_sub, "*.json"))):
        name = os.path.basename(p)
        if name in ("manifest.json", "index.json"):
            continue
        if name.startswith("index."):
            # per-game index files; handled separately
            continue
        if re.match(r"^\d+-\d+\.json$", name):
            paths.append(p)
    return paths


def regen_manifest_and_index(
    data_dir: str, log: Callable[[str], None] = print
) -> Dict[str, int]:
    """Rebuild data/manifest.json, data/index.json, and per-game indexes.

    Args:
        data_dir: path to the ModUpdateData repo root (the dir that contains
            ``data/``).
        log: line logger; defaults to print.

    Returns:
        dict with ``shards`` (int), ``mods`` (int), ``timestamps_fixed`` (int),
        ``per_game_indexed`` (int) — number of per-game index files written.
    """
    data_sub = os.path.join(data_dir, "data")
    if not os.path.isdir(data_sub):
        raise FileNotFoundError(f"missing data dir: {data_sub}")

    shard_paths = _shard_paths(data_dir)

    total = 0
    ts_fixed = 0
    by_game: Dict[str, int] = {g: 0 for g in GAME_ORDER}
    shard_entries: List[dict] = []
    # New global index entries: ordered by id ascending (sorted shards +
    # sorted records within each shard).
    index_pairs: List[Tuple[int, str]] = []
    per_game_pairs: Dict[str, List[Tuple[int, str]]] = {g: [] for g in GAME_ORDER}

    for path in shard_paths:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        new_text, changed = normalise_timestamps_text(text)
        ts_fixed += changed
        if changed:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)
        raw = new_text.encode("utf-8")
        mods = json.loads(new_text)
        for m in mods:
            game = m.get("game", "???")
            if game not in GAME_ORDER:
                # Unknown game tag: still tally it in by_game (informative)
                # but route the row to '???' for the index, so unknown rows
                # don't get lost. The validator will flag the row separately.
                by_game[game] = by_game.get(game, 0) + 1
                per_game_pairs.setdefault(game, [])
                game = "???"
            by_game[game] += 1
            mid = int(m["id"])  # validator will flag non-int ids separately
            updated = m.get("updated", "")
            index_pairs.append((mid, updated))
            per_game_pairs.setdefault(game, []).append((mid, updated))
        total += len(mods)
        rel = f"data/{os.path.basename(path)}"
        rng = os.path.basename(path)[:-len(".json")]
        shard_entries.append({
            "file": rel,
            "range": rng,
            "count": len(mods),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })

    # --- Global index ---
    index_pairs.sort(key=lambda p: p[0])
    index_path = os.path.join(data_sub, "index.json")
    index_obj = {str(mid): ts for mid, ts in index_pairs}
    index_text = json.dumps(index_obj, indent=2, ensure_ascii=False)
    # Re-normalize so the on-disk form is canon too (idempotent).
    index_text, _ = normalise_timestamps_text(index_text)
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(index_text)
        fh.write("\n")
    # Hash the on-disk content (incl. trailing newline) so manifest matches
    # what readers will fetch.
    with open(index_path, "rb") as fh:
        index_raw = fh.read()

    # --- Per-game index files ---
    per_game_index_entries: Dict[str, dict] = {}
    per_game_indexed = 0
    written_games: set[str] = set()
    for game in GAME_ORDER:
        pairs = sorted(per_game_pairs.get(game, []), key=lambda p: p[0])
        if not pairs:
            continue
        obj = {str(mid): ts for mid, ts in pairs}
        body = json.dumps(obj, indent=2, ensure_ascii=False)
        body, _ = normalise_timestamps_text(body)
        # Write as data/index.<GAME>.json. Game tags are uppercase ASCII so no
        # escaping concerns.
        out_path = os.path.join(data_sub, f"index.{game}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.write("\n")
        # Hash the on-disk content (incl. trailing newline) so manifest matches
        # what readers will fetch.
        with open(out_path, "rb") as fh:
            out_raw = fh.read()
        per_game_index_entries[game] = {
            "file": f"data/index.{game}.json",
            "bytes": len(out_raw),
            "sha256": hashlib.sha256(out_raw).hexdigest(),
        }
        per_game_indexed += 1
        written_games.add(game)

    # Sweep stale per-game index files (game with 0 rows this run but file
    # left from a previous regen). Only delete files that match the
    # data/index.<GAME>.json pattern and whose game tag is one we know about;
    # never touch index.json (global) or the shards.
    for p in glob.glob(os.path.join(data_sub, "index.*.json")):
        name = os.path.basename(p)
        # name is e.g. "index.FO4.json"; game tag is "FO4"
        game = name[len("index."):-len(".json")]
        if game not in written_games and game in GAME_ORDER:
            os.remove(p)
            log(f"regen: removed stale {name} (no rows for {game})")

    # --- Manifest update ---
    manifest_path = os.path.join(data_sub, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"missing {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    # Keep schema_version (1) and source. Refresh everything derived.
    manifest["schema_version"] = manifest.get("schema_version", 1)
    manifest["generated_at"] = _utc_now_iso()
    manifest["total_mods"] = total
    manifest["total_shards"] = len(shard_entries)
    manifest["shards"] = shard_entries
    manifest["index"] = {
        "file": "data/index.json",
        "bytes": len(index_raw),
        "sha256": hashlib.sha256(index_raw).hexdigest(),
    }
    # Stable by_game key order: GAME_ORDER first, then any unknown games we
    # encountered (preserved for visibility, validator will still fail on them).
    ordered_by_game: Dict[str, int] = {}
    for g in GAME_ORDER:
        if g in by_game:
            ordered_by_game[g] = by_game[g]
    for g in by_game:
        if g not in ordered_by_game:
            ordered_by_game[g] = by_game[g]
    manifest["by_game"] = ordered_by_game
    if per_game_index_entries:
        manifest["per_game_index"] = per_game_index_entries

    commit = _run_git_head(data_dir)
    if commit:
        manifest["commit"] = commit

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    log(
        f"regen: {len(shard_entries)} shards, {total} mods, "
        f"{ts_fixed} timestamps normalised, "
        f"{per_game_indexed} per-game indexes"
    )
    return {
        "shards": len(shard_entries),
        "mods": total,
        "timestamps_fixed": ts_fixed,
        "per_game_indexed": per_game_indexed,
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Rebuild ModUpdateData manifest + indexes in place."
    )
    ap.add_argument(
        "--data-dir",
        default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        help="path to the ModUpdateData repo root (default: parent of tools/)",
    )
    ap.add_argument("--quiet", action="store_true", help="suppress progress log")
    args = ap.parse_args(argv)
    log = (lambda *_a, **_k: None) if args.quiet else print
    regen_manifest_and_index(args.data_dir, log=log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
