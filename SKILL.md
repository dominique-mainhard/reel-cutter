---
name: reel-cutter
description: Cuts raw talking-head phone clips into a clean vertical reel (1080×1920) with Remotion. It keeps the LAST take of every line, removes silences, false starts and self-corrections, verifies every join by ear, adds punch-in zooms at changes of idea, finds real images and screenshots for what the speaker mentions, and places them with a subtle click sound. It evens out the audio cut by cut and renders at high quality. Use whenever the user asks to edit, cut or clean a reel/TikTok/short, "remove the silences", "cut the repeated takes", "keep the last take", "edit this video", or points at a folder of .MOV/.MP4 clips to edit, even without naming the skill or Remotion. Not for writing scripts, and it does not add captions or big animated text.
---

# Reel cutter (Remotion)

Turns raw talking-head clips into a clean vertical reel: the last take of every line, no dead air, reframing at changes of idea, and real screenshots or images with a click where they help. The cut, zooms, visuals and sound are all driven by data, so every change is a small edit and a re-render. This document is the craft. The code is in `template/` (Remotion project) and `scripts/` (analysis).

**First, if `local.md` exists next to this file, read it.** It holds this user's paths, language and preferences, and it overrides the defaults below. It is not part of the shared skill (gitignored).

Talk to the user in their language, briefly. **They decide the structure; you propose, with reasons.** Never render the final video before they approve the cut and the plan of visuals. Never overwrite their files: deliverables get new names next to the footage, and work files (`<workdir>`: transcripts, caches, stills) go in a scratch folder. Exception, by design: the speaker cutouts (`*-cutout-*.mov`) and Studio proxies (`proxy/`) are written into the video folder, because Remotion serves media only from there; delete them at the end (step 9).

What this skill does NOT do: captions/subtitles, big animated words, transitions between cuts, title cards or CTAs. If the user wants those, say so and let them add them in another tool.

## Setup (once per machine)

`<skill>` below is the folder this file is in. **Start every session with the preflight:**
```bash
<skill>/scripts/doctor.sh [<project>]
```
It checks every tool and prints the exact install command for anything missing. Show the user what's missing and **ask before installing** (the whisper model is a 1.6 GB download). Run it again until it says all required tools are installed.

- **Platform:** written for **macOS** (zsh scripts; the cutout uses CoreML, fastest on Apple silicon). On Linux or Windows (WSL), the Python scripts and Remotion work but the shell scripts need bash tweaks, and the cutout is slower. Say so before starting.
- **Required** (installed with [Homebrew](https://brew.sh) on a Mac):
  | Tool | Why | Install |
  |---|---|---|
  | Node ≥ 20 | Remotion | `brew install node` |
  | ffmpeg + ffprobe | probing, cutting, loudness | `brew install ffmpeg` |
  | Python 3 | the scripts (stdlib only; always run with `python3 -I`) | preinstalled, or `brew install python` |
  | whisper-cli (whisper.cpp) | transcription, runs locally | `brew install whisper-cpp` |
  | whisper model `ggml-large-v3-turbo.bin` | the transcription model | `mkdir -p ~/.whisper-models && curl -L -o ~/.whisper-models/ggml-large-v3-turbo.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin` (another path: set `WHISPER_MODEL`) |
- **Downloaded on first use, nothing to do:** `npx --yes hyperframes@0.9.68 remove-background` (the speaker cutout; local and free) and the Remotion packages (`npm install`).
- **Optional:** Google Chrome, only to capture articles and web pages (`capture_sources.mjs`; other location: set `CHROME_PATH`).
- **Language:** whisper uses `REEL_LANG` if set, else `"lang"` in `settings.local.json` (copy `settings.example.json`), else auto-detect.
- **Remotion project (once per user, reused for every video):**
  ```bash
  cp -R <skill>/template <project> && cd <project> && npm install && ./scripts/make_click.sh <mouse-click file> [<soft click file>]
  ```
  The click sounds are not shipped (licenses). Ask the user for a real recorded mouse click (e.g. a free one from pixabay.com; check its license allows published videos). Synthesized clicks sound fake.
  Remotion is free for individuals and companies of up to 3 people. Check https://www.remotion.dev/docs/license before telling anyone it's free.
- **Where:** `<project>` is one folder per user, reused for every video. Ask where they want it (suggest `~/reel-editor`) and write the answer in `local.md`.
- **Per video:** `mkdir -p <project>/public && ln -sfn "<video folder>" <project>/public/media`. Every media path in the data is `media/<file name>`, so source clips, screenshots, images, recordings and cutouts must all live in that folder. Use one folder per video.

## 0. Ask first (one message)

Before touching the footage, ask in **one** message only what you can't find out yourself (skip what `local.md` already answers):
1. **Where are the clips**, and are they all for this video?
2. **Language** spoken (sets `REEL_LANG`).
3. **Platform** (Instagram, TikTok, YouTube Shorts): sets the safe zone.
4. **Captures**: screenshots or screen recordings of anything they show or mention ("I asked the AI to…"), sent now if they have them.
5. **Is it sponsored?** If yes, a disclosure is needed; they define its wording.
6. Anything they already know they want (or don't): a max length, visuals they don't want.

Don't ask about choices the defaults below already cover; propose them in step 3 and let them change what they want.

## Workflow

### 1. Look
`ls` the folder and `ffprobe` every clip (resolution, fps, rotation, VFR, duration). Phone files with similar names (`IMG_1120.MOV` / `IMG_1120 2.MOV`) are usually **different takes**; check with `cmp` and duration. WhatsApp exports are often small, rotated and VFR: make a CFR vertical copy first.
- **Sources must be 9:16** (the Reel stretches each clip to 1080×1920). A landscape or 4:3 clip needs a cropped 9:16 copy first (`-vf crop=ih*9/16:ih,scale=1080:1920`); ask which part of the frame to keep.
- **iPhone HDR** (`ffprobe` shows `color_transfer=arib-std-b67`, HLG): compare the first still with the source; if colours look washed or wrong, make an SDR copy before editing.
- **A trimmed reference clip** ("use this one") marks where the cut starts by its **audio**: cross-correlate its first ~1 s of audio against the source and start there. Trimmed phone exports can start their audio a few frames before their video, so matching video frames can clip the first word.

### 2. Map the takes
```bash
python3 -I <skill>/scripts/takes.py <workdir> <clip1> <clip2> ...
```
This prints every speech region per clip, each transcribed on its own, sorted by **recording time** (`creation_time`), and writes `takes.json`.
- Transcribe per region, not per file: whisper's timestamps over a whole file drift 1–2 s after long pauses. Region edges come from `silencedetect`, so they are exact.
- **"Last take" means latest in time**, across files too. A clip recorded later supersedes an earlier clip with the same lines.
- Whisper mishears. Read for meaning, but **never "fix" what the person said**: their words are untouchable.

### 3. Propose the cut and wait for the OK
Give a table `# | clip | from–to | what stays` in final order, plus the total length. Mark mid-sentence points with `~`. Also say which takes are dropped and why, any reordering (e.g. the hook from a later clip), the filler words found (or say honestly that there are none), and what you need from them.

Propose the zooms with it (columns `time | line | zoom | why`):
- **Punch-in zoom at a change of idea.** Base framing is whatever the shot needs (often ~130% on 4K, centred on the face); the punch-in is about +12–15%.
  - Change framing only at a **new idea**, an emphasis, or to hide a visible jump cut.
  - Consecutive short cuts within one idea keep the **same** framing.
  - **At most one change every ~6–8 s.** Never ping-pong in/out on every cut: changing on almost every cut is dizzying.
  - Check framing on contact sheets (`ffmpeg … -vf scale=180:-1` per cut, then `tile=6x2`). If the face is near an edge, don't zoom.
- **Emphasis zoom = an instant JUMP, then back.** On the line that matters most, or one that contradicts or stresses what came before ("…and **no**, that's not how it works"), the framing jumps from the base to ~+10% with **no scaling animation**, and at the next cut it goes **back to the base**. Never leave the reel zoomed in.
  - Build it by splitting the cut at the dip just before the key word (`envelope.py`; `out` of the first piece = `in` of the second, so the audio stays continuous) and giving the second piece `zoom × 1.10` with no `zoomTo`. The next cut returns to the base `zoom`.
  - Same `center` on both pieces (never a pan). Usually one per reel.
  - A slow eased push-in (`zoomTo`/`zoomFrames`) and a fast animated punch (`"zoomEase": "out"`) still exist in the code, but they're not the default: a zoom that grows little by little reads as slow and forced. Use them only if the user asks.
- Cuts between clips are always plain cuts (no transitions).

### 4. Place the cuts precisely: `spec.json`
In/out times are **source seconds**. `sources` are **absolute paths to files inside the video folder** (the Remotion data keeps only the file name). `fps`: 23.976, 24, 25, 29.97, 30, 50, 59.94 or 60. A complete, valid example:
```json
{
  "name": "my-reel",
  "fps": 30, "width": 1080, "height": 1920,
  "sources": {"A": "/path/to/my-reel/IMG_0001.MOV", "B": "/path/to/my-reel/IMG_0002.MOV"},
  "cuts": [
    {"src": "B", "in": 1.92, "out": 4.40, "zoom": 1.3, "center": [0.5, 0.42], "label": "1 hook"},
    {"src": "B", "in": 6.10, "out": 8.02, "zoom": 1.3, "center": [0.5, 0.42], "label": "2 lead-in"},
    {"src": "B", "in": 8.02, "out": 9.85, "zoom": 1.43, "center": [0.5, 0.42], "label": "2 key words: jump zoom +10%"},
    {"src": "A", "in": 12.04, "out": 15.30, "zoom": 1.45, "center": [0.5, 0.4], "label": "3 new idea, punch-in"}
  ]
}
```
- `zoom`: scale of the source (1.0 = fit); `center`: source point (0–1) to centre (clamped so no black edge shows) and the anchor of the push-in; `zoomTo` + `zoomFrames` (default 60): eased pure scale from `zoom` to `zoomTo` within the cut (not the default, see step 3); `zoomEase: "out"` makes it a fast animated punch; `label` is for you.
- **Handles:** in ~0.08 s before speech; **out = where the last consonant really ends** (the level falls to the clip's noise floor + 4 dB for 60 ms, measured on the envelope) **+ 40 ms**. A fixed +0.12 s after silencedetect's end clips final consonants (s, t, d, r). Don't add more than that: extra tails read as dead air. **Words ending in "s" fade slowly**: whisper/silencedetect put the end too early and the cut swallows the s. Check the envelope after each out on those words and extend to where it falls under ~−55 dB (often +0.1–0.2 s). Only there: extending every cut brings back the dead air. Handles stay inside silence, never in a neighbouring take.
- **Self-corrections inside a sentence:** keep the last version. Cut in a stop-consonant gap (k/p/t) or a breath, found with `python3 -I <skill>/scripts/envelope.py <wav> <from> <to>`; dips below about −48 dB are safe. Words that glide together can't be split there: end the clip mid-glide and take the next word from the corrected take.

### 4b. Remove pauses and breaths INSIDE the takes
```bash
python3 -I <skill>/scripts/tighten.py <spec.json> <workdir> [--keep-last-end]
```
Step 4 only trims between lines; the pauses (0.3–0.6 s) and breaths inside each take stay, and they make the reel feel slow. `tighten.py` splits every cut at internal gaps ≥ 0.25 s (level under min(floor+22, −40 dB), which catches breaths) and keeps a consonant-safe tail (level under floor+8 for 60 ms, +40 ms) and an 80 ms pre-roll. Run it after the jump-zoom split: each piece keeps its cut's `zoom` and `center`. Cuts with `zoomTo` or `"noTighten": true` are left alone; `--keep-last-end` keeps the silence after the last line. Then step 5, always: no word may be lost. `normalize_cuts.py` gives the pieces of one take a single gain, so the level doesn't jump between them.

### 5. Verify the joins by ear
```bash
python3 -I <skill>/scripts/check_joins.py <spec.json> <workdir>
```
Read the transcript of the concatenated cut. A dropped or doubled word at a join means the point is off: fix it and re-run.

### 6. Plan the visuals and propose them before building
- **Aim for a visual at least every ~10 s.** Zooms don't count. Measure the gaps on the edited timeline, then propose a table `from–to | words | visual | source`.
- **Sources, in order of preference:**
  1. The person's own screenshots and screen recordings (ask for all of them in ONE message). Whenever they say "I asked <tool> to…" or "I built…", ask for that capture.
  2. **Real images you find**: the official logo or product screenshot of a tool they name (the company's site or press kit), the real web page of what they mention. Download the file into the video folder (`curl -L -o`), never hotlink. Check the image is what it claims to be and that using it is reasonable (logos and screenshots of a product being discussed usually are; stock photos and other people's photos need a license).
  3. **Captures of cited sources** (a study, survey, news story, law): see below.
  - Never invent: no fake screenshots, no made-up results, no AI-generated image presented as real.
- **When the video cites a study, survey, news story or law, find the real source and show it.** Don't wait to be asked.
  - Research it first (official page > primary report > reputable news). Check that it says what the person says; if it doesn't, tell them (verified vs not, with links) and let them decide. Never change their words.
  - Capture it with `scripts/capture_sources.mjs` (headless Chrome): the headline with its date, and the paragraph with the exact figure or sentence **highlighted in yellow**. Phone width (440 css, dpr 3) so the text is big enough to read in the reel. Crop tight; banners, cookie pop-ups and gallery arrows are hidden.
  - **Translate a page the audience can't read** with `"translate": "<lang>"`: it loads the real page through Google Translate. With `"top": true` the translate bar stays visible, which shows it's a translation. Prefer an edition of the same story in the audience's language when one exists.
  - **Prefer headlines over paragraphs.** A paragraph only when it carries the number that has to be seen.
  - Look at every capture before using it (`Read` the PNG): no pop-up, no cut line at the edge, highlight on the right words.
- **Readable size:** text in a capture must land at ≥ ~30 px in the 1080-wide reel. A 440-css/dpr-3 capture needs ≥ ~800 px of width on screen; small tiles are for headers or logos only.
- **Each visual appears exactly on the words it illustrates**, and when the person points or gestures toward it, on the frame the hand starts to move (check a 10 fps contact sheet of the source around the line).
- **The opening benefits from a visual**; its first visual enters ~0.5 s (15 frames) after the start, not on frame 0.
- **Visuals sit behind the head.** The person is cut out and stays in front of every layer (step 7). `front: true` draws a layer over the person instead (no cutout needed, faster).
- **"What am I showing?" test** before proposing any visual: a viewer with the sound off must get, in one look, what it shows AND why it's on that line. A pretty capture whose content is unrelated to the line doesn't belong.
- **Look: a hand-made collage** (`look: "collage"`, the default). Square corners, no frame, a faint shadow, **uneven sizes and alignment**, scattered in the empty space around the person. Tiles may overlap each other or the body, **never the face**, and several can accumulate as the person talks. Avoid grids, centring, identical sizes and shared edges (offset a tile ~40–60 px from the one above). Overlap only margins or a corner, never the content of the tile underneath. `look: "card"` (rounded white card) and `look: "plain"` (transparent PNGs, shadow follows the shape) are the alternatives.
  - White screenshots vanish against light walls: place them over darker areas or keep the shadow.
- **Screen recordings:** cut and time them with ffmpeg to the exact line (speed up long ones, keep it ≥ 0.8× when slowing down), CFR 30 fps, 1080 wide. On phone recordings, use `objectPosition` or `crop` to frame the part that matters.
- **Third parties:** skip screenshots that expose other people's names, contacts or messages unless that's the point, and blur them if needed.
- **Sound: a real click on every serious visual.**
  - A visual that appears on its own: `click.wav`, a mouse click.
  - A run of visuals one after another (3+ layers each within 2 s of the previous): `click-soft.wav`, the **same** subtler click on each, because the viewer hears it several times in a row. `Reel.tsx` does this by itself; `layer.click: "main" | "soft" | "none"` overrides.
  - **A group keeps a rhythm:** items that appear together enter at an **even 0.5 s interval** (15 frames: `first + 15·i`) and **all leave on the same frame**. Uneven gaps make the clicks lose their rhythm.
  - **Memes and jokes: no click and no pop.** `anim: "none"` cuts them in and out raw, with no sound.
  - Volume `clickVolume` 0.5 (soft plays at 0.8× that): noticeable but discreet; 0.2 is inaudible.
- **Safe zone: nothing that must be read goes under the platform's UI** (values measured on Instagram):
  - **Top: y ≥ 260** (profile header). **Sides: x 70–1010** (side crop). **Right buttons:** nothing to read at x > 915 below y ≈ 1040. **Bottom: y ≤ 1700** (username, caption, audio).
  - Run `python3 -I scripts/safe_zone.py src/data/<slug>.json` before every render; `--fix` moves each group of visuals down by the same amount (keeps the layout). Then check a contact sheet: moving down can put a tile behind the head.
- **Editing layers in the data JSON: match the exact file, never a substring** (removing `"chart-"` also deletes `chart-top.png`). Before every render, diff the layer list against the previous version (count, `src`, `from`) and explain every difference.
- **Sponsored video:** flag that a disclosure is needed. Don't write the disclosure copy.

### 7. Build in Remotion
```bash
cd <project>
python3 -I scripts/from_spec.py <spec.json> <slug>                    # cuts -> src/data/<slug>.json (+ index.ts)
# edit src/data/<slug>.json: layers (see "Data reference")
python3 -I scripts/cutouts.py <slug> [--force]                        # plate + speaker cutouts behind every layer window
python3 -I scripts/normalize_cuts.py src/data/<slug>.json            # one gain per take, to −20 LUFS
python3 -I scripts/proxies.py <slug>                                  # WebM copies so Studio can play HEVC/ProRes
npx remotion studio --port=3123                                       # live preview: http://localhost:3123/<slug>
```
- **Studio preview needs `proxies.py`.** Browsers can't play iPhone HEVC or ProRes 4444 cutouts ("MediaPlaybackError: Code 4"). The proxies (540×960 VP9, alpha kept) are used only inside Studio; renders and stills read the originals. Re-run it after `cutouts.py`.
- **Re-run `normalize_cuts.py` after every `from_spec.py`**: it regenerates the cuts and drops `gainDb`. `master.sh` printing an input far from −20 LUFS means this step was skipped.
- **After any re-cut, visuals keep their OLD frames**: save the data JSON first, then `python3 -I <skill>/scripts/remap_timeline.py <saved.json> src/data/<slug>.json`, then `normalize_cuts.py` and `cutouts.py --force`.
- `from_spec.py` keeps `layers` and `cutouts` when re-run, so you can re-cut without losing visuals.
- **`cutouts.py` loads the data at start and writes it at the end**: edits made to the JSON while it runs are overwritten. Edit after it finishes.
- `cutouts.py` renders `<slug>-base` (cut and zooms only), merges the windows of every layer (`front: true` layers are skipped), runs `remove-background` on each window (~80 ms/frame on Apple silicon) and writes `data.cutouts`. **Re-run with `--force` after any change to cuts or zooms**, because the plate changed.
- **Self-QA is not optional.** Take one still per visual and the hook (`npx remotion still <slug> --frame=<n> out/s<n>.png`), tile them with ffmpeg `hstack` and **look**: the head is in front of the layers, nothing is cut at the sides, the face is never covered. Render a low-res pass of animated sections (`--scale=0.25 --muted`) and check contact sheets. A defect visible in your own QA gets fixed before the user sees it.
- **Studio is for timing and layout, not for judging the cutout.** In the live preview the plate and the cutout are two videos that can drift a few frames, so the person may look doubled when moving. Full renders are frame-exact. **Stop the Studio server before the user watches a draft** (`pkill -f "remotion studio"`).
- For the user's review of motion, render a half-res draft: `npx remotion render <slug> out/draft.mp4 --scale=0.5 --crf=20`, master it, name it `…-DRAFT.mp4`.

### 8. Render, master, verify
```bash
npx remotion render <slug> out/<slug>-raw.mp4 --codec=h264 --crf=14 --jpeg-quality=95 --audio-bitrate=320k
./scripts/master.sh out/<slug>-raw.mp4 "<video folder>/<name>-final.mp4"   # linear gain → −16 LUFS + peak limiter −1.5 dBFS, video copied
```
- CRF 14 with JPEG 95 comes out at ~20 Mb/s. Remotion's defaults (JPEG 80, CRF 18) look softer.
- **Audio:** takes often differ by several dB. `normalize_cuts.py` evens them out at **−20 LUFS** (headroom for quiet phone takes), and `master.sh` brings the mix to **−16 LUFS** with linear gain and a transparent limiter. Report the I/LRA/Peak it prints. Not `loudnorm`: when it can't stay linear it silently compresses, which sounds canned. Platforms don't publish an official loudness target.
- Then check the duration against the timeline, a contact sheet of ~8 frames, and the loudness.

### 9. Deliver
Give the final MP4 path, a table of what is where (time → words → visual), the final loudness, and anything still pending (missing captures).
- Delete big intermediates (plates, draft renders, proxies). Keep the cutouts only while the video may still change.
- **Cleanup never deletes what a re-edit needs:** the source clips, the captures and images, `spec.json` and `src/data/<slug>.json` stay. Say what was kept.
- **Re-editing a delivered video:** never work from the exported final. Start from the raw clips and the saved `spec.json`.

## Data reference (`src/data/<slug>.json`)

All times are in **frames** on the edited timeline; all positions and sizes in **px on the 1080×1920 frame**. To place a visual on a word, find the word's time in the per-cut transcript (`takes.json` regions or `check_joins.py`) and convert it to timeline frames (cut `from` + offset inside the cut). A worked example of the hand-written keys:
```json
{
 "layers": [
  {"kind": "image", "src": "media/apps.png", "from": 120, "dur": 75, "look": "collage",
   "box": {"left": 140, "top": 300, "width": 520, "height": 700, "objectPosition": "50% 0%"}},
  {"kind": "video", "src": "media/rec-timer.mp4", "from": 300, "dur": 110,
   "box": {"left": 560, "top": 300, "width": 420, "height": 760}, "crop": {"x": 0, "y": 0, "w": 1, "h": 0.6}},
  {"kind": "image", "src": "media/meme.png", "from": 450, "dur": 40, "anim": "none",
   "box": {"left": 90, "top": 320, "width": 460, "height": 460}}
 ],
 "clickVolume": 0.5
}
```
- `cuts[]`: generated: `src, from, dur, srcIn, zoom, center`, optional `zoomTo` + `zoomFrames` + `zoomEase`, and `gainDb` (from `normalize_cuts.py`).
- `layers[]`: `{kind: "image"|"video", src, from, dur, box: {left, top, width, height, objectPosition?}, crop?: {x,y,w,h}, look?: "collage"|"card"|"plain", anim?: "pop"|"none", click?: "main"|"soft"|"none", front?}`. `crop` is a fraction (0–1) of the source. `anim: "none"` also silences the click unless `click` is set.
- `cutouts[]`: written by `cutouts.py`. `clickVolume`: default 0.5.

## Gotchas
- **zsh:** no word-splitting in `for r in "1 2"`; write `${a}`, not `$a:end` (`:e` is a modifier); macOS screenshot names contain U+202F, so use globs.
- **ffmpeg:** `atrim` takes decimals, not fractions; some builds lack `drawtext`; put `-an`/codec flags after the inputs.
- **Remotion:** composition ids are letters, digits and dashes only; `OffthreadVideo` `volume` may exceed 1; `transparent` is needed for alpha .mov.
- **Two videos at once:** `public/media` is one symlink, so editing a second video repoints it. Before re-rendering, check where it points; if it's another video, render from a copy of the project with its own `public/media`.
