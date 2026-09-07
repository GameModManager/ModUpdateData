# Schema

Version: 1

## Manifest (`data/manifest.json`)

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-06T00:00:00Z",
  "source": "migrated (2024-08-04)",
  "total_mods": 7277,
  "total_shards": 36,
  "shard_size": 1000,
  "shards": [{ "file": "data/00000-00999.json", "range": "00000-00999", "count": 467, "bytes": 259989, "sha256": "..." }],
  "index": { "file": "data/index.json", "bytes": 260125, "sha256": "..." },
  "by_game": { "SE": 2940, "LE": 4328, "FO4": 0, "SF": 0, "OB": 0, "OBR": 0, "S4": 0, "S3": 0, "???": 9 },
  "per_game_index": {
    "SE": { "file": "data/index.SE.json", "bytes": 102586, "sha256": "..." },
    "LE": { "file": "data/index.LE.json", "bytes": 148071, "sha256": "..." }
  }
}
```

## Shard (`data/XXXXX-XXXXX.json`)

Array of mod records, sorted by `id` ascending.

```json
{
  "id": 25905,
  "canonical": 25905,
  "title": "...",
  "category": "Adult Mods",
  "game": "SE",
  "href": "25905-...",
  "status": "unknown",
  "version": "1.0.0",
  "updated": "2023-02-20T07:50:59Z",
  "sortable": "...",
  "tags": ["2b", "werewolf"],
  "source": "migrated",
  "automated": false,
  "update_history": ["2023-02-20T07:50:59Z"],
  "obsolete_reason": ["..."],
  "obsolete_successor": ["..."],
  "obsolete_alternative": ["..."],
  "note": ["..."],
  "other_link": [{ "href": "https://...", "text": "..." }]
}
```

Fields:

- `id` (int) - LoversLab file id
- `canonical` (int) - grouping key, `id == canonical` is display row
- `title` (string)
- `category` (string) - LL category
- `game` (string) - one of:

  | Value | Game                       | Notes                                     |
  | ----- | -------------------------- | ----------------------------------------- |
  | `SE`  | Skyrim Special Edition     | Default. Existing dataset rows.            |
  | `LE`  | Skyrim Legendary Edition   | Legacy Skyrim (pre-SE). Existing rows.    |
  | `FO4` | Fallout 4                  | RSS-discovered.                           |
  | `SF`  | Starfield                  | RSS-discovered.                           |
  | `OB`  | Oblivion                   | RSS-discovered.                           |
  | `OBR` | Oblivion Remastered        | Kept separate from `OB` for clarity.      |
  | `S4`  | The Sims 4                 | RSS-discovered.                           |
  | `S3`  | The Sims 3                 | RSS-discovered.                           |
  | `???` | unknown / undetermined     | Legacy fallback. Prefer retag over keep.  |

  Values are uppercase. Validator (`validate.py` → `ALLOWED_GAME`) fails closed
  on any other value. Adding a new game requires both the validator set and
  this table.
- `href` (string, optional) - LL file slug without prefix
- `status` (string) - `unknown`, `compatible`, `incompatible`, `deleted`, `ported`, `convertible`, `obsolete`, etc.
- `version` (string)
- `updated` (string) - ISO-8601 UTC
- `sortable` (string, optional) - lowercased title for sorting
- `tags` (string[], optional) - mod keywords
- `source` (string) - data origin (`migrated` for initial import, `loverslab` for RSS-discovered)
- `automated` (bool) - `false` for curated, `true` for RSS-discovered awaiting review
- `update_history` (string[]) - ordered ISO-8601 timestamps
- `last_checked` (string, optional) - ISO-8601 UTC of the last check, updated on every check even when nothing changed. Absent on legacy rows.
- `obsolete_reason`, `obsolete_successor`, `obsolete_alternative` (string[], optional)
- `note` (string[], optional)
- `other_link` (object[], optional) - `{href, text?}`

## Index (`data/index.json`)

```json
{
  "123": "2023-02-20T07:50:59Z",
  "456": "2024-07-26T15:13:06Z"
}
```

Mapping `file_id (string) -> updated (ISO-8601)`.

## Multi-Game Schema

The dataset is multi-game. Every record carries a `game` tag (see field table
above). Sharding and the canonical `id` are **site-global** and never reshuffle
by game — LoversLab file ids are site-unique, so a Fallout 4 mod and a Skyrim
mod can sit in the same shard without conflict. New RSS-discovered records are
stamped with the correct game at discovery time; existing rows keep their
historical tag (no retroactive re-tag is required).

### Feed-of-origin

Every record's `game` value comes from the **feed it was discovered on**, not
from a constant. Each LoversLab RSS feed maps 1:1 to exactly one game value:

| Feed (forum id + slug)                                  | Game  |
| ------------------------------------------------------- | ----- |
| `69-...-skyrim-special-edition-adult-mods.xml`          | `SE`  |
| `70-...-skyrim-special-edition-non-adult-mods.xml`      | `SE`  |
| `315-...-sexlab-framework-se.xml`                       | `SE`  |
| `63-...-fallout-4-adult-sex-mods.xml`                   | `FO4` |
| `62-...-fallout-4-non-adult-mods.xml`                   | `FO4` |
| `308-...-advanced-animation-framework.xml`              | `FO4` |
| `571-...-starfield-adult-sex-mods.xml`                  | `SF`  |
| `572-...-starfield-non-adult-mods.xml`                  | `SF`  |
| `18-...-oblivion-adult-sex-mods.xml`                    | `OB`  |
| `44-...-oblivion-non-adult-mods.xml`                    | `OB`  |
| `16-...-lovers-with-pk.xml`                             | `OB`  |
| `644-...-oblivion-remastered-adult-mods.xml`            | `OBR` |
| `66-...-the-sims-4.xml`                                 | `S4`  |
| `438-...-cas-sims.xml`                                  | `S4`  |
| `55-...-the-sims-3.xml`                                 | `S3`  |

Cross-posted mods (rare) are tagged from the feed they were first seen on;
breadcrumb verify on first page check may retag and re-stamp, logged.

### Per-Game Index Plan

The current global `data/index.json` (id → updated) is canonical and stays
unchanged. To keep per-game poll payloads small for the GMM client and the
Pages site, we will publish derived per-game index files:

- `data/index.<GAME>.json` — same shape, filtered to rows where `game == GAME`.
  Generated alongside the manifest; not hand-edited.
- `data/manifest.json` gains a `by_game` count and a `per_game_index` map:

  ```json
  {
    "by_game": { "SE": 5400, "LE": 1800, "FO4": 0, "SF": 0, "OB": 0, "OBR": 0, "S4": 0, "S3": 0, "???": 0 },
    "per_game_index": {
      "SE": { "file": "data/index.SE.json", "bytes": ..., "sha256": ... }
    }
  }
  ```

`???` rows are counted under `???` until a backfill retags them. Once the
per-game index files exist (see Workspace-fn4i), the validator will verify
`sum(by_game) == total_mods` and that each per-game index file exists,
parses, and is a strict subset of the global index.

Shard files stay **global id-ranged** (`floor(id / 1000)`). Per-game shard
splitting is rejected: it would lose id locality and duplicate range files.

Backwards compatibility: clients reading the v1 manifest ignore the new
fields. Schema version stays at 1 with additive fields; bump to 2 only if a
breaking change is introduced.

## Sharding

- Bucket: `floor(id / 1000)`
- File: `data/XXXXX-XXXXX.json` where XXXXX is zero-padded 5 digits
- A mod's shard never moves (stable).

## Sorting

Mods inside shards sorted by `id` numeric ascending. Manifest shards sorted by range.
