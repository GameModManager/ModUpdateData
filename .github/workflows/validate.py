#!/usr/bin/env python3
"""Validate ModUpdateData dataset: schema, sorted, ISO dates, shard hashes."""
import json, pathlib, hashlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ALLOWED_STATUS = {"unknown","compatible","incompatible","deleted","ported","new","convertible","needs-patch","obsolete","legacy-compatible"}
ALLOWED_GAME = {"SE","LE","???"}

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
    total += len(mods)
    # also verify index
if manifest.get("total_mods") != total:
    errors.append(f"manifest total_mods {manifest.get('total_mods')} != actual {total}")

# index
index_path = DATA / "index.json"
if index_path.exists():
    idx = json.loads(index_path.read_text())
    if len(idx) != total:
        errors.append(f"index size {len(idx)} != total {total}")
    for k,v in idx.items():
        if not k.isdigit():
            errors.append(f"index key not numeric {k!r}")
        check_iso(v, f"index {k}")

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
print(f"OK: {total} mods, {len(manifest.get('shards',[]))} shards validated")
