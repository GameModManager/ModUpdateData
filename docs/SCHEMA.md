# Schema

Version: 1

## Manifest (`data/manifest.json`)

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-02T00:00:00Z",
  "source": "tasairis/compat-data (2024-08-04)",
  "total_mods": 7277,
  "total_shards": 36,
  "shard_size": 1000,
  "shards": [{ "file": "data/00000-00999.json", "range": "00000-00999", "count": 467, "bytes": 259505, "sha256": "..." }],
  "index": { "file": "data/index.json", "bytes": 250969, "sha256": "..." }
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
  "source": "tasairis",
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
- `game` (string) - `SE`, `LE`, `???`
- `href` (string, optional) - LL file slug without prefix
- `status` (string) - `unknown`, `compatible`, `incompatible`, `deleted`, `ported`, `convertible`, `obsolete`, etc.
- `version` (string)
- `updated` (string) - ISO-8601 UTC
- `sortable` (string, optional) - lowercased title for sorting
- `tags` (string[], optional) - from tasairis `tag`
- `source` (string) - `tasairis` for migrated, `rss` or `scrape` for future
- `automated` (bool) - `false` for curated, `true` for RSS-discovered awaiting review
- `update_history` (string[]) - ordered ISO-8601 timestamps
- `last_checked` (string, optional) - ISO-8601 UTC of the last scraper check, written on every check even when nothing changed. Absent on migrated rows.
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

## Sharding

- Bucket: `floor(id / 1000)`
- File: `data/XXXXX-XXXXX.json` where XXXXX is zero-padded 5 digits
- A mod's shard never moves (stable).

## Sorting

Mods inside shards sorted by `id` numeric ascending. Manifest shards sorted by range.
