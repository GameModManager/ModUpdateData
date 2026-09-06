#!/usr/bin/env python3
"""Validate ModUpdateData dataset: schema, sorted, ISO dates, shard hashes,
and per-game index artifacts."""
import json, pathlib, hashlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ALLOWED_STATUS = {"unknown","compatible","incompatible","deleted","ported","new","convertible","needs-patch","obsolete","legacy-compatible"}
# Game values:
#   SE  - Skyrim Special Edition
#   LE  - Skyrim Legendary Edition (legacy)
#   FO4 - Fallout 4
#   SF  - Starfield
#   OB  - Oblivion
#   OBR - Oblivion Remastered
#   S4  - The Sims 4
#   S3  - The Sims 3
#   ???  - legacy fallback for rows whose game could not be determined
ALLOWED_GAME = {"SE","LE","FO4","SF","OB","OBR","S4","S3","???"}

errors = []

def check_iso(s, ctx):
    if not ISO_RE.match(s):
        errors.append(f"{ctx}: bad ISO-8601 {s!r}")

# manifest
manifest_path = DATA / "manifest.json"
if not manifest_path.exists():
    errors.append("missing data/manifest.json")
    sys.exit(1)

manifest = json.loads(manifest_path.read_text())
for k in ["schema_version","generated_at","total_mods","total_shards","shards"]:
    if k not in manifest:
        errors.append(f"manifest missing {k}")

total = 0
game_counts = {}
for shard in manifest.get("shards", []):
    f = shard.get("file","")
    p = ROOT / f
    if not p.exists():
        errors.append(f"shard missing file {f}")
        continue
    raw = p.read_bytes()
    if shard.get("bytes") != len(raw):
        errors.append(f"{f}: bytes mismatch manifest {shard.get('bytes')} vs actual {len(raw)}")
    h = hashlib.sha256(raw).hexdigest()
    if shard.get("sha256") != h:
        errors.append(f"{f}: sha256 mismatch")
    mods = json.loads(raw.decode())
    # sorted by id
    ids = [m["id"] for m in mods]
    if ids != sorted(ids):
        errors.append(f"{f}: not sorted by id")
    # check range
    lo, hi = map(int, shard["range"].split("-"))
    for m in mods:
        mid = m["id"]
        if not (lo <= mid <= hi):
            errors.append(f"{f}: id {mid} out of range {lo}-{hi}")
        if not isinstance(mid, int):
            errors.append(f"{f}: id not int {mid!r}")
        if "updated" in m:
            check_iso(m["updated"], f"{f} id {mid} updated")
        for d in m.get("update_history", []):
            check_iso(d, f"{f} id {mid} update_history")
        if m.get("status") not in ALLOWED_STATUS:
            errors.append(f"{f} id {mid}: unknown status {m.get('status')!r}")
        if m.get("game") not in ALLOWED_GAME:
            errors.append(f"{f} id {mid}: unknown game {m.get('game')!r}")
        if "automated" not in m or not isinstance(m["automated"], bool):
            errors.append(f"{f} id {mid}: missing or non-bool automated")
        if "source" not in m:
            errors.append(f"{f} id {mid}: missing source")
        # tally for by_game cross-check
        g = m.get("game")
        if g in ALLOWED_GAME:
            game_counts[g] = game_counts.get(g, 0) + 1
    total += len(mods)
    # also verify index
if manifest.get("total_mods") != total:
    errors.append(f"manifest total_mods {manifest.get('total_mods')} != actual {total}")

# by_game cross-check
manifest_by_game = manifest.get("by_game", {})
if not isinstance(manifest_by_game, dict):
    errors.append("manifest by_game must be an object")
else:
    if sum(manifest_by_game.values()) != total:
        errors.append(
            f"manifest by_game sum {sum(manifest_by_game.values())} != total {total}"
        )
    for g, n in manifest_by_game.items():
        actual = game_counts.get(g, 0)
        if actual != n:
            errors.append(f"manifest by_game[{g}]={n} != actual {actual}")
    for g in game_counts:
        if g not in manifest_by_game:
            errors.append(f"manifest by_game missing game {g}")

# index
index_path = DATA / "index.json"
idx = {}
if index_path.exists():
    idx = json.loads(index_path.read_text())
    if len(idx) != total:
        errors.append(f"index size {len(idx)} != total {total}")
    for k,v in idx.items():
        if not k.isdigit():
            errors.append(f"index key not numeric {k!r}")
        check_iso(v, f"index {k}")
else:
    errors.append("missing data/index.json")

# per-game index files: subset of global, hash matches manifest entry.
per_game_index = manifest.get("per_game_index", {})
if not isinstance(per_game_index, dict):
    errors.append("manifest per_game_index must be an object")
else:
    for g, entry in per_game_index.items():
        if g not in ALLOWED_GAME:
            errors.append(f"per_game_index key {g!r} not in ALLOWED_GAME")
        rel = entry.get("file", "") if isinstance(entry, dict) else ""
        if not rel or not rel.startswith("data/"):
            errors.append(f"per_game_index[{g}] bad file {rel!r}")
            continue
        p = ROOT / rel
        if not p.exists():
            errors.append(f"per_game_index[{g}] missing file {rel}")
            continue
        raw = p.read_bytes()
        if entry.get("bytes") != len(raw):
            errors.append(
                f"per_game_index[{g}]: bytes mismatch "
                f"manifest {entry.get('bytes')} vs actual {len(raw)}"
            )
        h = hashlib.sha256(raw).hexdigest()
        if entry.get("sha256") != h:
            errors.append(f"per_game_index[{g}]: sha256 mismatch")
        sub = json.loads(raw.decode())
        if not isinstance(sub, dict):
            errors.append(f"per_game_index[{g}]: not a JSON object")
            continue
        for k, v in sub.items():
            if k not in idx:
                errors.append(f"per_game_index[{g}]: key {k} not in global index")
            elif idx[k] != v:
                errors.append(
                    f"per_game_index[{g}]: value for {k} differs from global"
                )
            check_iso(v, f"per_game_index[{g}] {k}")
        if len(sub) != game_counts.get(g, 0):
            errors.append(
                f"per_game_index[{g}]: size {len(sub)} != by_game count "
                f"{game_counts.get(g, 0)}"
            )
    # Every game with rows must have a per_game_index entry (catch stale
    # manifests that were regenerated without the new fields).
    for g, n in game_counts.items():
        if n > 0 and g not in per_game_index:
            errors.append(f"per_game_index missing entry for game {g} ({n} rows)")
    # And every per_game_index entry must have rows.
    for g in per_game_index:
        if game_counts.get(g, 0) == 0:
            errors.append(f"per_game_index[{g}] present but no rows in dataset")

# bucket (optional)
bucket_dir = ROOT / "bucket"
if bucket_dir.exists():
    for p in bucket_dir.glob("*.json"):
        if p.name == "README.md":
            continue
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            errors.append(f"bucket/{p.name}: invalid JSON {e}")
            continue
        fid = data.get("file_id") or p.stem
        if not str(fid).isdigit():
            errors.append(f"bucket/{p.name}: file_id not numeric {fid!r}")

if errors:
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
per_game_msg = ""
if per_game_index:
    per_game_msg = f", {len(per_game_index)} per-game indexes"
print(
    f"OK: {total} mods, {len(manifest.get('shards',[]))} shards"
    f", {len(per_game_index)} per-game indexes validated"
)

