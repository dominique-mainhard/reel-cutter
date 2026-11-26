# reel-cutter

A [Claude Code](https://claude.com/claude-code) skill that cuts raw talking-head phone clips into a clean vertical reel (1080×1920) with [Remotion](https://www.remotion.dev):

- keeps the **last take** of every line and drops false starts and self-corrections
- removes **silences**, with handles that don't clip final consonants, and checks every join by ear
- adds **punch-in zooms** at changes of idea (sparingly), plus an instant **jump zoom** (~+10%, then back) on the key line
- finds **real images and screenshots** for what the speaker mentions (their own captures, official logos and product pages, highlighted captures of cited articles) and places them as a collage behind the speaker's head, each with a **click** sound
- evens out the audio cut by cut and masters it to −16 LUFS

It does not add captions, big animated text or transitions.

## Install

```bash
git clone https://github.com/dominique-mainhard/reel-cutter ~/.claude/skills/reel-cutter
~/.claude/skills/reel-cutter/scripts/doctor.sh
```

Then ask Claude Code to edit a folder of clips ("edit the clips in ~/Videos/my-reel"). The skill walks through the setup on first use. Written for macOS. Everything runs locally (whisper.cpp for transcription, a local background-removal model for the cutout).

Click sounds are not included: bring a real recorded mouse click whose license allows published videos (for example from pixabay.com).

Remotion has its own license (free for individuals and small companies): https://www.remotion.dev/docs/license

## Make it yours

Fork it and change whatever you want. Personal settings go in `local.md` and `settings.local.json` next to `SKILL.md`; both are gitignored.
