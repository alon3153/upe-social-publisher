# Arcads API call log

`arcads-api.jsonl` is an append-only JSON Lines record of every Arcads
generation call, written by `scripts/render_sofia_arcads.py`. It is the primary
source for credit-cost estimates on later batches, since Arcads exposes no
billing endpoint.

Two rows are written per generation. The create row:

```json
{"ts":"2026-09-22T09:00:00Z","batch":"week2","adId":"rome_power",
 "assetId":"...","model":"seedance-2.0","duration":15,"resolution":"720p",
 "aspectRatio":"9:16","audioEnabled":true,"referenceImagesCount":0,
 "promptWordCount":257,"type":"seedance_20"}
```

The completion row, after polling finishes:

```json
{"ts":"2026-09-22T09:05:12Z","batch":"week2","adId":"rome_power","assetId":"...",
 "response":{"status":"generated","creditsCharged":720,"videoUrl":"https://...",
             "thumbnailUrl":null,"error":null}}
```

Never log prompt text, API keys or Authorization headers. To estimate the cost
of a new batch, match on `model` plus the same `duration`, `resolution` and
`referenceImagesCount`, and read `creditsCharged` off the completion row.
