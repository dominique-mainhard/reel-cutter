#!/bin/zsh
# Preflight: checks every tool the reel workflow needs and prints how to install what is missing.
# Usage: <skill>/scripts/doctor.sh [<remotion project dir>]     Exit code = number of missing required items.
model=${WHISPER_MODEL:-$HOME/.whisper-models/ggml-large-v3-turbo.bin}
chrome=${CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}
miss=0
ok()   { print "  ok      $1"; }
need() { print "  MISSING $1\n          -> $2"; miss=$((miss+1)); }
opt()  { print "  missing $1 (optional: $2)\n          -> $3"; }

print "System"
[[ $(uname) == Darwin ]] && ok "macOS $(sw_vers -productVersion) $(uname -m)" || print "  warning not macOS: the scripts are written for macOS/zsh; the cutout (CoreML) may be slow or fail"
command -v brew >/dev/null && ok "Homebrew" || opt "Homebrew" "easiest way to install the rest" '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'

print "Required"
if command -v node >/dev/null; then
  v=(${(s:.:)$(node -v | tr -d v)}); if (( v[1] >= 24 || (v[1] == 22 && v[2] >= 13) || (v[1] == 20 && v[2] >= 19) )); then ok "node $(node -v)"; else need "node 20.19+, 22.13+ or 24+ (found $(node -v))" "brew install node"; fi
else need "node 20.19+, 22.13+ or 24+" "brew install node"; fi
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && ok "ffmpeg + ffprobe" || need "ffmpeg + ffprobe" "brew install ffmpeg"
command -v python3 >/dev/null && ok "python3 $(python3 -V 2>&1 | cut -d' ' -f2)" || need "python3" "brew install python   (or: xcode-select --install)"
command -v whisper-cli >/dev/null && ok "whisper-cli" || need "whisper-cli (whisper.cpp, transcription)" "brew install whisper-cpp"
[[ -f $model ]] && ok "whisper model $model" || need "whisper model at $model (1.6 GB)" "mkdir -p ~/.whisper-models && curl -L -o ~/.whisper-models/ggml-large-v3-turbo.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"

print "Optional"
[[ -x $chrome ]] && ok "Google Chrome (source captures)" || opt "Google Chrome" "only to capture cited articles with capture_sources.mjs" "install Chrome, or set CHROME_PATH"
print "  note    the speaker cutout runs 'npx --yes hyperframes@0.9.68 remove-background' (downloads on first use, runs locally, free)"

if [[ -n $1 ]]; then
  print "Project $1"
  [[ -d $1/node_modules/remotion ]] && ok "npm install done" || need "Remotion packages" "cd '$1' && npm install"
  [[ -f $1/public/sfx/click.wav ]] && ok "click sound" || need "public/sfx/click.wav" "cd '$1' && ./scripts/make_click.sh <a mouse-click sound file>"
  [[ -L $1/public/media ]] && ok "public/media -> $(readlink "$1/public/media")" || print "  note    public/media not linked yet: ln -sfn \"<video folder>\" '$1/public/media'"
fi
print ""; (( miss == 0 )) && print "All required tools are installed." || print "$miss required item(s) missing. Install them (ask the user first), then run this again."
exit $miss
