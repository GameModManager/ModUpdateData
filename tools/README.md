# tools/

Pipeline scripts for ModUpdateData. Pure-Python, stdlib only (no dependencies).

## regen.py

Rebuilds `data/manifest.json` (with `by_game` counts and `per_game_index`
entries), `data/index.json` (id-sorted, canonically-stamped), and per-game
index files (`data/index.<GAME>.json`). Normalises any `+0000` / `+HH:MM`
zone designators to canonical `Z` in shard and index files along the way.

Run from the repo root:

```
python3 tools/regen.py
```

Idempotent. Safe to re-run; only writes when something changed.
