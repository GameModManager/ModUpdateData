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

### Scraper hook

The scraper (`projects/scraper/scrape.py`) currently ships its own
`regen_manifest_and_index()`. To avoid drift, that function should be
delegated to this module:

```python
import sys
sys.path.insert(0, "/path/to/ModUpdateData/tools")
from regen import regen_manifest_and_index
regen_manifest_and_index(data_dir)
```

The signature here matches the scraper's (data_dir, log=print). After
the scraper is updated to import this, deleting the scraper's copy is
the next step (filed as a follow-up scraper change; do not touch the
scraper repo from this ticket).
