# Bucket

The bucket defines all tracked mods. One file per mod: `bucket/<id>.json`

```json
{ "file_id": "12345", "added_by": "github-username", "added_at": "2026-09-02T00:00:00Z" }
```

- PRs add files to `bucket/` to request tracking of a new mod.
- The scraper reads `bucket/` as the tracking set (plus all mods already in `data/` shards).
- For the initial release the bucket is empty - all 7277 migrated mods are already tracked in `data/`.
- Validation workflow checks numeric id and JSON validity.

Future: `bucket/` may be populated explicitly for all tracked mods (one file per mod) for easier PR review.
