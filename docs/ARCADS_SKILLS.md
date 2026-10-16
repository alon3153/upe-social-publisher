# Arcads skill pack

Six agent skills for generating AI marketing creative (video, static image ads,
YouTube thumbnails) through the [Arcads](https://arcads.ai/?via=claude-code)
external API, plus publishing the results as paused Meta ads.

## Provenance

| | |
|---|---|
| Upstream | `github.com/krusemediallc/arcads-claude-code` |
| Commit installed | `0bfafb256cfce3ff4447d7ea1611a37f0af536be` |
| License | MIT |

Skill files are byte-identical to upstream. Nothing was edited on the way in, so
a future re-sync is a plain copy.

## What is installed

| Skill | Purpose |
|---|---|
| `arcads-external-api` | Video and image generation: Seedance 2.0, Sora 2, Veo 3.1, Kling 3.0, Grok Video, Nano Banana, b-roll, scenes. The entry point for most work. |
| `chatgpt-image-ad` | Static Meta image creatives via ChatGPT Image 2. Typography-heavy and UI-mimicry layouts. |
| `nano-banana-image-ad` | Static Meta image creatives via Nano Banana 2 / Pro. Photoreal and lifestyle layouts. |
| `image-ad-clone` | Reverse-engineers an existing image ad into a reusable prompt template. |
| `generate-youtube-thumbnail` | High-CTR YouTube thumbnails via Nano Banana 2. |
| `meta-ad-builder` | Publishes a finished creative as a PAUSED Meta ad via the Marketing API. |

## Layout

Follows the convention already used by the other skills in this repo.

- `.agents/skills/<name>/` holds the skill content.
- `.claude/skills/<name>` symlinks to it.
- `.agents/shared/skills/` holds prompting guides that several skills link to
  (the 37-template image-ad prompt library, pixar-style and claymation ad
  pipelines, caption-video, gemini-omni-flash).
- `.claude/shared` symlinks to `.agents/shared` so the skills' relative
  `../../shared/...` links resolve from either path.
- `skills-lock.json` records all six. The `computedHash` values are a SHA-256 of
  each `SKILL.md` computed at install time.

## Setup

Credentials go in `.env` at the repo root, which is gitignored. Copy the
template and fill in your key:

```bash
cp .agents/shared/arcads.env.example .env   # then edit
```

Get the key at [app.arcads.ai/settings/api](https://app.arcads.ai/settings/api).
`ARCADS_BASIC_AUTH` is the more reliable of the two auth options; `ARCADS_API_KEY`
works for most accounts but returns 403 on some. The Meta variables are only
needed for `meta-ad-builder`.

Verify before the first generation call:

```bash
curl -u "$ARCADS_API_KEY:" https://external-api.arcads.ai/v1/products
```

## Reference media

The skills read and write character sheets, product photos, and style boards
under `references/`. That media is local-only and gitignored, with
`references/README.md` kept as the folder-naming guide. The upstream repo ships
119 MB of example influencer and product images which were deliberately not
imported. Clone upstream if you want them.

## Extra dependencies

The image-ad generators are Python stdlib only. Beyond that:

- `ffmpeg` and `jq` for the pixar-style, claymation, and caption-video pipelines
- `openai-whisper` for caption transcription
- `pip install -r .agents/skills/meta-ad-builder/scripts/requirements.txt` for Meta publishing

## Known upstream issue

`arcads-external-api/prompting/analyze-video/SKILL.md` links to `seedance-2.md`
as a sibling, but the file lives in `../prompt-library/`. The broken link was
left in place to keep the files identical to upstream.
