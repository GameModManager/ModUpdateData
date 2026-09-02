# ModUpdateData

Public mod update and compatibility dataset for LoversLab and beyond. Tracks update history, compatibility, and metadata for Skyrim (LE/SE) and other games.

Source: migrated from [tasairis/compat-data](https://github.com/tasairis/compat-data) (7280 mods, last updated 2024-08-04). Original site: [tasairis.github.io/compat](https://tasairis.github.io/compat/).

## Dataset

- **Sharded JSON** in `data/` - ID-range sharding (1000 per shard, 36 shards for 7277 mods), stable and diff-friendly.
- **Manifest** `data/manifest.json` - schema version, total counts, per-shard hashes and sizes.
- **Index** `data/index.json` - lightweight `file_id -> updated` map for fast auto-check (~245 KB).
- Each mod record keeps full tasairis fields plus `source`, `automated`, and `update_history` (list of ISO-8601 timestamps, first entry is the tasairis `updated` date).

## Schema

Per-mod record:

```json
{
  "id": 25905,
  "canonical": 25905,
  "title": "Example Mod",
  "category": "Adult Mods",
  "game": "SE",
  "href": "25905-example-mod",
  "status": "unknown",
  "version": "1.0.0",
  "updated": "2023-02-20T07:50:59Z",
  "update_history": ["2023-02-20T07:50:59Z"],
  "tags": ["tag1", "tag2"],
  "source": "tasairis",
  "automated": false
}
```

Optional fields preserved from tasairis: `obsolete_reason`, `obsolete_successor`, `obsolete_alternative`, `note`, `other_link`, `sortable`. See `docs/SCHEMA.md`.

- `automated: false` - curated (migrated from tasairis). Future RSS-discovered mods will be `true` until human review.
- `update_history` - ordered list of ISO-8601 timestamps when the mod was observed to update.
- `canonical` - grouping key; `id == canonical` is the display row (others are LE/SE counterparts).

## Fetching (client)

```js
// 1. Fetch manifest
const m = await fetch("https://raw.githubusercontent.com/GameModManager/ModUpdateData/main/data/manifest.json").then(r=>r.json());
// 2. Fast path: index for date check
const index = await fetch("https://raw.githubusercontent.com/GameModManager/ModUpdateData/main/data/index.json").then(r=>r.json());
// 3. Detail: shard containing file_id
const shard = `data/${String(Math.floor(id/1000)*1000).padStart(5,"0")}-${String(Math.floor(id/1000)*1000+999).padStart(5,"0")}.json`;
```

Mirrors (fallback order): `raw.githubusercontent.com` -> `gamemodmanager.github.io/ModUpdateData` (Pages) -> local clone.

## Web View

GitHub Pages: https://gamemodmanager.github.io/ModUpdateData/ - sortable table (ID, SE Status, Category, Mod, Last Updated), detail popup. Backed by `data/manifest.json` + shards.

## Contributing

- **Bucket**: `bucket/` holds one file per tracked mod. PRs adding mods go there; see `bucket/README.md`.
- **Edits**: edit the shard JSON directly (pretty-printed, sorted by `id`). CI validates schema, numeric ids, ISO dates.
- **Scraping**: scraping logic is private (Pi + local scripts). Do not commit scrapers to this public repo.

## License

Dataset facts are from public LoversLab pages via tasairis. This repo is public domain / CC0 where applicable. Respect LoversLab ToS.

## Acknowledgments

Thanks to tasairis for the original compat dataset and site.
