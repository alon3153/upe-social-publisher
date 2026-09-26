# Sofia UGC batch — week2

Five UGC ads for Uproduction Events, built on the Sofia presenter persona and
ready to render through the Arcads external API.

**Nothing has been generated yet.** The repo has no `.env`, so there are no
Arcads credentials in this environment. The batch is written, validated and
waiting on two approvals plus a key.

## The five ads

Each follows the format that already works for Sofia: one named city, one
specific operational trap, the fix, the authority line, the follow CTA.

| # | City | The trap | The fix |
|---|---|---|---|
| 1 | Rome | Heritage villas have heritage electrical capacity. Full AV plus a live catering kitchen trips the house supply, and the unbudgeted generator appears at load-in. | Power survey and available amperage in writing before signing. Generator as its own budget line. |
| 2 | Santorini | Caldera arrivals depend on tenders and ferries. One afternoon of meltemi wind and 150 guests are still on the water. | Design the arrival around the weather window, not the sunset photo. Contract a land-side backup. |
| 3 | Milan | Salone del Mobile, the fashion weeks and EICMA empty the room stock and multiply rates. Minimum-stay rules appear. | Check the fair calendar before locking dates. One week's shift is often the biggest saving available. |
| 4 | Marrakech | Riads are small by design. A 200-person programme splits across six of them, so you run six operations. | One anchor property for the group. Riads for the leadership tier only. |
| 5 | Iceland | Around the December solstice Reykjavik gets roughly four hours of usable light, which removes the outdoor programme. | Move to February or March for aurora season with workable daylight, or design for the dark. |

All five claims are general operational realities of the meetings and incentive
travel trade, not assertions about any named venue. That matches how the two
published Sofia films treat Prague and Barcelona.

## Files

| Path | What it is |
|---|---|
| `content/sofia/prompts/week2.json` | The batch. Per ad: Seedance prompt, dialogue beats, overlay cards, caption, target accounts and date. |
| `scripts/render_sofia_arcads.py` | Renders the batch and writes the queue file the existing pipeline consumes. |
| `scripts/brand_video_overlay.py` | Burns the caption cards, wordmark and site line onto a rendered clip. |
| `assets/fonts/Comfortaa[wght].ttf` | The brand font, vendored with its OFL licence so the overlay runs anywhere. |
| `logs/README.md` | Schema for the Arcads call log that future cost estimates read. |

## How to ship it

```bash
cp .agents/shared/arcads.env.example .env    # then add your key
python3 scripts/render_sofia_arcads.py week2 --dry-run   # payloads + cost, no calls
python3 scripts/render_sofia_arcads.py week2             # generate

# brand each clip, then queue the batch for approval
python3 scripts/brand_video_overlay.py raw.mp4 branded.mp4 --batch week2 --ad rome_power
python3 scripts/enqueue_sofia.py week2
```

The render step writes `content/sofia/queue/week2.json` with the same six keys
`scripts/enqueue_sofia.py` already reads, so approval and publishing are
unchanged. Days 9003 to 9007 do not collide with week1's 9001 and 9002.

`brand_video_overlay.py` reproduces the look of the published films: rounded
translucent caption cards in the upper third, the wordmark top-left and
`upe.co.il` bottom-right. Cards whose first line starts with a number render in
brand yellow `#FBCE0A`, which is how the published films mark the fix steps;
everything else is white. Cards spread evenly across the clip unless you pass
`--timings`. It reads the card text straight from the batch file via `--ad`, or
takes literal text with `--cards`.

Two things it needs: `ffmpeg` on PATH (it falls back to the `imageio-ffmpeg`
package) and the Comfortaa font, which is now vendored at `assets/fonts/` under
its OFL licence. The older `scripts/brand_overlay.py`, which composites still
images, still points at a Dropbox path that only resolves on one Mac; the video
overlay deliberately does not, so it runs in CI.

## Cost

Seedance 2.0 at 720p is billed by the second and is the expensive part.

| | |
|---|---|
| Per clip, 15s | ~720 credits |
| Batch of 5 | **~3,600 credits** |

Treat that as an estimate only. The vendor reference contradicts itself: its
summary table says 0.06 credits/sec, while a later note dated 2026-05-19 says
that figure was wrong by two orders of magnitude and the real rate is ~48
credits/sec, re-tested across eight production runs. The script uses the newer
figure because it is newer and explicitly supersedes the table. Confirm the real
rate in the Arcads platform before spending.

A cheap way to de-risk: render one clip first with `--only rome_power`, read the
actual `creditsCharged` out of `logs/arcads-api.jsonl`, then decide on the
other four.

## Two gates before generating

The skill requires both, and neither has been satisfied:

1. **Dialogue approval.** The spoken lines are in `content/sofia/prompts/week2.json`
   under `dialogue`, 27 to 31 words each, which is 11 to 12.5 seconds at a
   relaxed pace and leaves room for the silent beat inside 15 seconds.
2. **Credit confirmation.** The number above. The script will not generate
   without `--yes` or an interactive confirmation.

## Two judgement calls worth reviewing

**These are rawer than the published Sofia films.** The two films already live
are polished presenter pieces: even lighting, smooth framing, B-roll inserts. A
UGC ad works by not looking like an ad, so these prompts specify handheld
framing, uneven light, phone-mic audio with room tone, and visible grain. Same
persona, same authority, lower production gloss. If you want them to match the
existing films instead, the tone and technical-flaw paragraphs are the parts to
change.

**Sofia is locked by text, not by a reference image.** Seedance holds character
continuity best from a reference still, and there is no clean one. Every frame
of `content/sofia/videos/sofia_barcelona_01.mp4` carries a burned-in caption
card across her face, so no usable portrait can be extracted. Instead all five
prompts repeat one identical `persona_lock` description taken from that film:
early thirties, dark brown shoulder-length wavy hair in a soft side part, warm
olive skin, light brown eyes, small gold hoops, cream linen blazer over a camel
knit top.

Worth doing before the next batch: generate a proper Sofia character sheet with
the `arcads-external-api` skill's character-sheet flow, at image prices rather
than video prices, and keep the hero still as a permanent reference. Every later
render then gets real continuity for a few credits.

## One inconsistency to settle

The repo states the brand's track record two different ways:

- `content/sofia/` captions and `content/days/day100`: **15 years, 200+ events, 120+ countries**
- `content/video_scripts/*.json`: **1,500 events across 130+ destinations**

This batch uses the first, because that is what the published Sofia captions
say. The two cannot both be right on a public feed, so it is worth picking one.
