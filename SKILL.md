---
name: reel-cutter
description: Cuts raw talking-head phone clips into a clean vertical reel (1080×1920) with Remotion. It keeps the LAST take of every line, removes silences, false starts and self-corrections, verifies every join by ear, writes word-exact captions (checked by an independent subagent before any draft), adds punch-in zooms at changes of idea, finds real images and screenshots for what the speaker mentions, and places them with a subtle click sound. It evens out the audio cut by cut and renders at high quality. Use whenever the user asks to edit, cut or clean a reel/TikTok/short, "remove the silences", "cut the repeated takes", "keep the last take", "add captions", "edit this video", or points at a folder of .MOV/.MP4 clips to edit, even without naming the skill or Remotion. Not for writing scripts, and it does not add big animated text.
---

# Reel cutter (Remotion)

Turns raw talking-head clips into a clean vertical reel: the last take of every line, no dead air, word-exact captions, reframing at changes of idea, and real screenshots or images with a click where they help. The cut, captions, zooms, visuals and sound are all driven by data, so every change is a small edit and a re-render. This document is the craft. The code is in `template/` (Remotion project) and `scripts/` (analysis, captions, cutouts).

**First, if `local.md` exists next to this file, read it.** It holds this user's paths, language and preferences, and it overrides the defaults below. It is not part of the shared skill (gitignored).

Talk to the user in their language, briefly. **They decide the structure; you propose, with reasons.** Never render the final video before they approve the cut and the plan of visuals. Never overwrite their files: deliverables get new names next to the footage, and work files (`<workdir>`: transcripts, caches, stills) go in a scratch folder. Exception, by design: the speaker cutouts (`*-cutout-*.mov`) and Studio proxies (`proxy/`) are written into the video folder, because Remotion serves media only from there; delete them at the end (step 10).

What this skill does NOT do: big animated words, transitions between cuts, title cards or CTAs. If the user wants those, say so and let them add them in another tool.

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
2. **Language and dialect** spoken (sets `REEL_LANG`; captions keep the exact forms they say, regional ones included).
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
  - Same `center` on both pieces (never a pan): a pure scale. A different center, or one the edge clamp pushes elsewhere at the new zoom, also moves the frame and the person is no longer where they were (`qa_check.py` flags it as PAN). Usually one per reel.
  - It starts on the **first word** of the line, not mid-line: split the previous cut at the dip before that word.
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
  ],
  "captions": {
    "maxWords": 4, "punctuation": "question", "lowercaseStart": false, "leadFrames": 1,
    "fixes": [["open ai", "OpenAI"]], "breaks": ["the whole|team"], "joins": [], "properNouns": ["New York"]
  }
}
```
- `zoom`: scale of the source (1.0 = fit); `center`: source point (0–1) to centre (clamped so no black edge shows) and the anchor of the push-in; `zoomTo` + `zoomFrames` (default 60): eased pure scale from `zoom` to `zoomTo` within the cut (not the default, see step 3); `zoomEase: "out"` makes it a fast animated punch; `label` is for you; `"noCaptions": true` on a silent cut (a sped-up screen recording) keeps whisper from inventing words over it.
- `captions` (all optional, see step 6): `punctuation` `"question"` (keep only ?, the default), `"none"` or `"keep"`; `lowercaseStart` true starts every cue lowercase (except proper nouns); `fixes`, `breaks`, `joins`, `properNouns`.
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

### 6. Captions (every video)
```bash
python3 -I <skill>/scripts/make_captions.py <spec.json> "<video folder>/<name>.srt" <workdir>
```
Each cut is transcribed on its own and shifted to its timeline position, with a per-cut cache. It also writes `<workdir>/words.json` (`{text, frame, cut}` per word, timeline frames), handy for placing visuals on a word. **Read every line it prints**, then fix things in `spec.json → captions` and run it again:
- `fixes`: mishearings (`[["heard", "said"]]`).
- `breaks`: `"left|right"` for awkward splits.
- `joins`: `"left|right"` keeps two words in one cue across a short pause that would otherwise split them (only short pauses: a joined word shows early).
- `properNouns`: names that keep their capital and, if multi-word ("New York"), are never split across cues. English "I"/"I'm" are always kept.

Fixes and proper nouns that apply to **every** video of this user (dialect forms whisper "corrects" to the standard form, brand names) go once in `fixes` / `properNouns` of `settings.local.json`. Only unambiguous fixes, and only forms the user confirmed they say.

Rules:
- **The text matches exactly what was said**, dialect included. Whisper swaps words that change the meaning; when a word doesn't make sense in context, re-transcribe that short window, and ask only if it stays ambiguous. Never "improve" their words.
- **3–4 words per cue, max** (`maxWords: 4`, the default): short, fast-changing cues read as dynamic; 5–6 words read as long. **Group by MEANING**: a cue is a chunk that belongs together ("in fact", "4 out of 10", "on a social network"), never a split inside one ("in | fact", "4 out | of 10"). Read the whole cue list and add `breaks` until every cue is a natural chunk; expect many on a long reel. A **one-word cue** is allowed only when breaks isolate it on both sides (`"says|OpenAI"`, `"OpenAI|the company"`).
- **A cue never shows words before they're said.** Each cue enters 1 frame before its first word (`leadFrames`), is never shorter than 4 frames, and prefers to change where the picture cuts. A new cue starts at any pause > 0.4 s (and when the next word starts > 1 s after the previous one, because whisper stretches word ends over silence). A fix that adds a missing word must anchor on the word it precedes (`["there one", "because there one"]`), not span the pause before it, or the added word gets an early timestamp.
- **Whisper drops or doubles short words between runs**: the per-cut cache keeps one version, so add a fix only after reading that version, or the word comes out twice.
- **Whisper is weakest after a shot change, over music, and in long fluent stretches** (cues collapse to 2 frames, or run ~0.5 s early). Check those cues against the audio with `envelope.py` and re-time them.
- **One size, always** (56 px in `Reel.tsx`; the font and size are set once at the top of the file). A cue that doesn't fit in 860 px **wraps to a second line**, it never shrinks: changing sizes from cue to cue looks inconsistent.
- **Captions never touch the face: they sit below the chin.** Make a contact sheet of the edited cut with guide lines (`drawbox` at 1150/1250/1350), take the lowest chin (leaning forward, zooms included) and set `data.captionTop` ≈ chin + 80 px (1240 is a common value on a seated medium shot). Over a white shirt or wall, set a stronger `captionShadow`. A per-cue `top` moves one cue (e.g. a laptop fills the lower half).
- **Manual caption edits in the data JSON are lost on every `from_spec.py`** (it re-reads the .srt): fix the .srt or the spec instead, or script the edit and re-apply it after each re-cut.
- **After any re-cut, run `make_captions.py` again before `from_spec.py`**: the old .srt times no longer match the cut.

Hand over the `.srt` too, for uploading to platforms.

### 7. Plan the visuals and propose them before building
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
- **Visuals sit behind the head.** The person is cut out and stays in front of every layer (step 8). `front: true` draws a layer over the person instead (no cutout needed, faster).
- **"What am I showing?" test** before proposing any visual: a viewer with the sound off must get, in one look, what it shows AND why it's on that line. A pretty capture whose content is unrelated to the line doesn't belong.
- **Look: a hand-made collage** (`look: "collage"`, the default). Square corners, no frame, a faint shadow, **uneven sizes and alignment**, scattered in the empty space around the person. Tiles may overlap each other or the body, **never the face**, and several can accumulate as the person talks. Avoid grids, centring, identical sizes and shared edges (offset a tile ~40–60 px from the one above). Overlap only margins or a corner, never the content of the tile underneath. `look: "card"` (rounded white card) and `look: "plain"` (transparent PNGs, shadow follows the shape) are the alternatives.
  - White screenshots vanish against light walls: place them over darker areas or keep the shadow.
- **Screen recordings:** cut and time them with ffmpeg to the exact line (speed up long ones, keep it ≥ 0.8× when slowing down), CFR 30 fps, 1080 wide. On phone recordings, use `objectPosition` or `crop` to frame the part that matters.
- **Personal data is blurred without asking**: addresses, cross streets, postcodes, card digits, order numbers, ID numbers, other people's names, emails and messages. Skip a screenshot that exposes third parties unless that's the point. Check the blur at 100 %: it covers each item completely, no first letter leaking at the edge.
- **Check what the speaker claims about a product against its official docs** before building the visual (e.g. "the bot can't see your card" vs docs saying a saved card is visible to it). Never change their words: show them the quote + link and let them cut, keep or re-record the line.
- **When the line names a detail, the visual shows that detail on that word** ("…and when I hover, you see it up close" → the close-up exactly then): re-time the screen recording piecewise (slow the idle part, 1× from the moment that matters) so the event lands on the line.
- **Crop with context:** a capture must stay recognizable (keep the app's header or title bar, not a bare chat bubble), and memes/screenshots lose their black borders (check the edge columns at 100 %, not on a thumbnail).
- **Product images on a flat studio background** (a grid of generated bags, garments, shoes): cut each item out with `python3 -I <skill>/scripts/cutout_products.py <image> <outdir> --grid 4x2 [--strong 3]` (colour key; the person model fails on objects) and float them: `look: "plain"`, `box.rotate` ±2–5°, uneven offsets, optional `drift` (a few px of slow float), entering 0.5 s apart, all leaving together. Not a rectangle with the grid.
- **The speaker small over a screen or B-roll (picture-in-picture):** cut them out so they float, never a rounded box. Crop the source above furniture, run `remove-background` on it, then `python3 -I <skill>/scripts/clean_cutout.py <cutout.mov> <source> <out.mov> --crop W:H:X:Y [--mouth x0,y0,x1,y1]` (opaque body, no halo, holes and a dark handheld mic filled, colours from the source). Use it as a `video` layer with `front: true`, `look: "plain"`, anchored to the frame's bottom corner (alpha `.mov`/`.webm` layers render transparent). Check it over flat green on several frames.
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

### 8. Build in Remotion
```bash
cd <project>
python3 -I scripts/from_spec.py <spec.json> <slug> <captions.srt>     # cuts + captions -> src/data/<slug>.json (+ index.ts)
# edit src/data/<slug>.json: layers (see "Data reference")
python3 -I scripts/cutouts.py <slug> [--force]                        # plate + speaker cutouts behind every layer window
python3 -I scripts/normalize_cuts.py src/data/<slug>.json            # one gain per take, to −20 LUFS
python3 -I scripts/proxies.py <slug>                                  # WebM copies so Studio can play HEVC/ProRes
npx remotion studio --port=3123                                       # live preview: http://localhost:3123/<slug>
```
- **Studio preview needs `proxies.py`.** Browsers can't play iPhone HEVC or ProRes 4444 cutouts ("MediaPlaybackError: Code 4"). The proxies (540×960 VP9, alpha kept) are used only inside Studio; renders and stills read the originals. Re-run it after `cutouts.py`.
- **Re-run `normalize_cuts.py` after every `from_spec.py`**: it regenerates the cuts and drops `gainDb`. `master.sh` printing an input far from −20 LUFS means this step was skipped.
- **After any re-cut, visuals keep their OLD frames**: save the data JSON first, then `python3 -I <skill>/scripts/remap_timeline.py <saved.json> src/data/<slug>.json`, then `normalize_cuts.py` and `cutouts.py --force`.
- `from_spec.py` keeps `layers`, `cutouts`, `captionTop`, `captionShadow` and `hold` when re-run, so you can re-cut or re-caption without losing visuals. The captions always come from the .srt you pass.
- **`cutouts.py` loads the data at start and writes it at the end**: edits made to the JSON while it runs are overwritten. Edit after it finishes.
- **`cutouts.py` reuses files by window name:** after changing a zoom or a clip inside one window, delete only that window's `.mov` (or `--force` when the cut changed everywhere), or the cutout keeps the old framing. Cutouts are the heaviest step after the render: never `--force` the whole set when only a few windows changed.
- `cutouts.py` renders `<slug>-base` (cut and zooms only), merges the windows of every layer (`front: true` layers are skipped), runs `remove-background` on each window (~80 ms/frame on Apple silicon) and writes `data.cutouts`. **Re-run with `--force` after any change to cuts or zooms**, because the plate changed.
- **Self-QA is not optional.** Take one still per visual and the hook (`npx remotion still <slug> --frame=<n> out/s<n>.png`), tile them with ffmpeg `hstack` and **look**: the head is in front of the layers, nothing is cut at the sides, the face is never covered. Render a low-res pass of animated sections (`--scale=0.25 --muted`) and check contact sheets. A defect visible in your own QA gets fixed before the user sees it.
- **Studio is for timing and layout, not for judging the cutout.** In the live preview the plate and the cutout are two videos that can drift a few frames, so the person may look doubled when moving. Full renders are frame-exact. **Stop the Studio server before the user watches a draft** (`pkill -f "remotion studio"`).
- **QA gate before EVERY draft.** Most corrections a user sends are things a careful pass would have caught:
  1. `python3 -I scripts/qa_check.py src/data/<slug>.json` must say `qa OK`. It catches cues shorter than 6 frames (collapsed whisper timing), a jump zoom that also pans, missing media and a caption line too low; it also lists captions sharing their band with a visual and gaps of more than 10 s without a visual.
  2. **Every caption cue read against the audio** where whisper is weak (step 6), and every word makes sense in context.
  3. **Every capture at 100 %**: blur complete, no black borders, enough context to recognize the app.
  4. **Every visual's in/out against the words it illustrates**: it enters on the word that names it and leaves when the next idea starts.
  5. **Independent caption review by a subagent.** You wrote the captions, so you read what you expect. Before showing ANY draft, give a fresh subagent the cues exactly as they will show (timeline seconds) and the draft's audio (`ffmpeg -i out/draft.mp4 -vn -ac 1 -ar 16000 <workdir>/review.wav`), and tell it the language and dialect. It reads the whole script as a story (every word must make sense in context and in the speaker's dialect), re-transcribes in short windows, and measures the first-word onset of every doubtful cue with `envelope.py` (a cue shows within −0.1/+0.15 s of its first word, never before it). It reports problems only; you fix them, run the gate again, then render. Don't hand it your conclusions: it's there to catch what you missed.
- **Draft budget: ONE full draft, then only correction clips.** A full draft of a 2–3 min reel takes minutes at every core and makes a laptop's fans loud, and most review rounds change only a few spots. So:
  1. The first full draft goes out only after the whole QA gate. Render it at half res: `npx remotion render <slug> out/draft.mp4 --scale=0.5 --crf=20 --concurrency=4`, master it, name it `…-DRAFT.mp4`.
  2. Don't render until the user's feedback is complete: dictated messages often get cut off mid-sentence and a second message follows. Apply what's clear in the data meanwhile; if a message looks cut off, ask "anything else?" before rendering.
  3. Each later round: fix everything, run the gate again, then render ONLY the fixed spots: `./scripts/fix_clips.sh <slug> "<video folder>/<slug>-FIXES.mp4" <from>-<to> …` (timeline seconds, as in the .srt; 1 s of context each side, half res, 2 threads at low priority, mastered). Tell the user which spot is which, in order.
  4. The next full render is the final. Re-render a full draft only if the cut itself changed (lines removed or moved), because then the timing moved everywhere.

### 9. Render, master, verify
```bash
npx remotion render <slug> out/<slug>-raw.mp4 --codec=h264 --crf=14 --jpeg-quality=95 --audio-bitrate=320k
./scripts/master.sh out/<slug>-raw.mp4 "<video folder>/<name>-final.mp4"   # linear gain → −16 LUFS + peak limiter −1.5 dBFS, video copied
```
- CRF 14 with JPEG 95 comes out at ~20 Mb/s. Remotion's defaults (JPEG 80, CRF 18) look softer.
- **Audio:** takes often differ by several dB. `normalize_cuts.py` evens them out at **−20 LUFS** (headroom for quiet phone takes), and `master.sh` brings the mix to **−16 LUFS** with linear gain and a transparent limiter. Report the I/LRA/Peak it prints. Not `loudnorm`: when it can't stay linear it silently compresses, which sounds canned. Platforms don't publish an official loudness target.
- Then check the duration against the timeline, a contact sheet of ~8 frames, and the loudness.

### 10. Deliver
Give the final MP4 path, the `.srt` path, a table of what is where (time → words → visual), the final loudness, and anything still pending (missing captures).
- Delete big intermediates (plates, draft renders, proxies). Keep the cutouts only while the video may still change.
- **Cleanup never deletes what a re-edit needs:** the source clips, the captures and images, `spec.json`, the `.srt` and `src/data/<slug>.json` stay. Say what was kept.
- **Re-editing a delivered video:** never work from the exported final (captions and visuals are burned in). Start from the raw clips and the saved `spec.json`.

## Data reference (`src/data/<slug>.json`)

All times are in **frames** on the edited timeline; all positions and sizes in **px on the 1080×1920 frame**. To place a visual on a word, take its frame from `<workdir>/words.json` (written by `make_captions.py`), or find it in the per-cut transcript and convert it (cut `from` + offset inside the cut). A worked example of the hand-written keys:
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
 "clickVolume": 0.5,
 "captionTop": 1240
}
```
- `cuts[]`: generated: `src, from, dur, srcIn, zoom, center`, optional `zoomTo` + `zoomFrames` + `zoomEase`, and `gainDb` (from `normalize_cuts.py`).
- `captions[]`: generated from the .srt: `{from, to, text}`, optional `top` (per-cue override).
- `captionTop`: y of the caption line, below the chin (step 6; default 1240). `captionShadow`: CSS text-shadow for captions (a stronger one over a white shirt or wall).
- `layers[]`: `{kind: "image"|"video", src, from, dur, box: {left, top, width, height, objectPosition?, rotate?}, crop?: {x,y,w,h}, look?: "collage"|"card"|"plain", anim?: "pop"|"none", click?: "main"|"soft"|"none", front?, drift?}`. `crop` is a fraction (0–1) of the source. `anim: "none"` also silences the click unless `click` is set. `box.rotate`: degrees (scattered cutouts). `drift`: px of slow float. Video layers in `.mov`/`.webm` with alpha render transparent.
- `hold: {src, frames}`: a still shown after the last cut, so the last word isn't cut off when it lands at the very end of the source (e.g. `frames: 24`). Export the still from the last frame of the last cut; `from_spec.py` extends `durationInFrames` by `frames`.
- `cutouts[]`: written by `cutouts.py`. `clickVolume`: default 0.5.

## Gotchas
- **zsh:** no word-splitting in `for r in "1 2"`; write `${a}`, not `$a:end` (`:e` is a modifier) or `$n:layout` in a filter string (`:l`); always `${n}`. macOS screenshot names contain U+202F, so use globs.
- **ffmpeg:** `atrim` takes decimals, not fractions; some builds lack `drawtext`; put `-an`/codec flags after the inputs. **`-sseof` can write nothing and still exit 0** (e.g. the last frame for `hold`): use `-ss <duration − 0.1>` and check the file exists.
- **A replaced opening clip shifts everything after it:** shift every layer `from` after the join by the frame difference, then `make_captions.py`, `from_spec.py`, `normalize_cuts.py` and `cutouts.py --force`.
- **Remotion:** composition ids are letters, digits and dashes only; `OffthreadVideo` `volume` may exceed 1; `transparent` is needed for alpha .mov.
- **Two videos at once:** `public/media` is one symlink, so editing a second video repoints it. Before re-rendering, check where it points; if it's another video, render from a copy of the project with its own `public/media`.
