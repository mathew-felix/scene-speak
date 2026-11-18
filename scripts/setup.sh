#!/usr/bin/env bash
# SceneSpeak one-command setup for macOS (Apple Silicon or Intel).
#
#   ./scripts/setup.sh            install everything, then launch server + iOS Simulator
#   ./scripts/setup.sh --no-run   install only
#
# Safe to re-run: every step skips work that is already done.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_AFTER=1
[[ "${1:-}" == "--no-run" ]] && RUN_AFTER=0

bold() { printf "\n\033[1m==> %s\033[0m\n" "$*"; }
ok()   { printf "  \033[32mok\033[0m  %s\n" "$*"; }
die()  { printf "\n\033[31mERROR:\033[0m %s\n\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. system
bold "1/7 Checking your Mac"
[[ "$(uname -s)" == "Darwin" ]] || die "SceneSpeak needs macOS (the iOS Simulator only runs on a Mac)."
ok "macOS $(sw_vers -productVersion) ($(uname -m))"

RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
[[ $RAM_GB -ge 8 ]] || die "At least 8 GB RAM is required (found ${RAM_GB} GB)."
ok "${RAM_GB} GB RAM"

FREE_GB=$(df -g "$ROOT" | awk 'NR==2{print $4}')
[[ $FREE_GB -ge 12 ]] || die "At least 12 GB free disk space is required (found ${FREE_GB} GB)."
ok "${FREE_GB} GB free disk"

[[ -d /Applications/Xcode.app ]] || die "Xcode is not installed. Install it from the Mac App Store, open it once, then re-run this script."
if ! xcodebuild -version >/dev/null 2>&1; then
  echo "  Xcode needs to be selected and its license accepted (asks for your Mac password):"
  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
  sudo xcodebuild -license accept
  sudo xcodebuild -runFirstLaunch || true
fi
xcodebuild -version >/dev/null 2>&1 || die "Xcode is installed but not usable. Open Xcode once, accept its prompts, then re-run."
ok "$(xcodebuild -version | head -1)"

if ! xcrun simctl list runtimes 2>/dev/null | grep -q "iOS"; then
  die "No iOS Simulator runtime found. Open Xcode > Settings > Components (or Platforms), download an iOS runtime, then re-run."
fi
ok "iOS Simulator runtime available"

# ------------------------------------------------------------ 2. homebrew
bold "2/7 Homebrew and system tools"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$b" ]] && eval "$("$b" shellenv)" && break
  done
fi
command -v brew >/dev/null 2>&1 || die "Homebrew is not installed. Install it from https://brew.sh (one command), then re-run."
ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"

brew_need() { # brew_need <formula> <command-to-check>
  if command -v "$2" >/dev/null 2>&1; then ok "$1 already installed"; else echo "  installing $1 ..."; brew install "$1"; fi
}
brew_need node node
brew_need cocoapods pod
brew_need llama.cpp llama-server
brew_need watchman watchman

# python 3.12 is required: newer versions lack wheels for some dependencies
if ! brew list python@3.12 >/dev/null 2>&1; then echo "  installing python@3.12 ..."; brew install python@3.12; fi
PY="$(brew --prefix python@3.12)/bin/python3.12"
[[ -x "$PY" ]] || die "python@3.12 was not found at $PY"
ok "$("$PY" --version)"

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
[[ $NODE_MAJOR -ge 20 ]] || die "Node 20+ is required (found $(node -v)). Run: brew upgrade node"
ok "Node $(node -v)"

# ------------------------------------------------------------- 3. js deps
bold "3/7 App dependencies (npm)"
npm install --no-audit --no-fund
ok "node_modules ready"

# ------------------------------------------------------------ 4. python
bold "4/7 Server dependencies (Python)"
if [[ ! -x server/.venv/bin/python ]] || ! server/.venv/bin/python --version 2>&1 | grep -q "3.12"; then
  rm -rf server/.venv
  "$PY" -m venv server/.venv
fi
server/.venv/bin/python -m pip install --quiet --upgrade pip
server/.venv/bin/python -m pip install --quiet -r server/requirements.txt
ok "virtualenv ready"

# ------------------------------------------------------------ 5. models
bold "5/7 AI models (about 2.2 GB, resumable)"
mkdir -p models
download() { # download <url> <dest> <min-bytes>
  local url="$1" dest="$2" min="$3" size=0
  [[ -f "$dest" ]] && size=$(stat -f%z "$dest")
  if [[ $size -ge $min ]]; then ok "$(basename "$dest") already downloaded"; return; fi
  echo "  downloading $(basename "$dest") ..."
  local try
  for try in 1 2 3 4 5; do
    if curl -fL -C - --progress-bar -o "$dest" "$url"; then break; fi
    echo "  retry $try ..."; sleep 3
  done
  size=$(stat -f%z "$dest" 2>/dev/null || echo 0)
  [[ $size -ge $min ]] || die "Download of $(basename "$dest") failed or is incomplete. Check your internet and re-run."
}
HF="https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main"
download "$HF/Qwen3.5-2B-Q4_K_M.gguf" models/Qwen3.5-2B-Q4_K_M.gguf 1280000000
download "$HF/mmproj-F16.gguf"        models/mmproj-F16.gguf        668000000

if [[ -f models/kokoro-multi-lang-v1_0/model.onnx ]]; then
  ok "Kokoro voice model already installed"
else
  download "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2" \
           models/kokoro-multi-lang-v1_0.tar.bz2 349000000
  tar -xjf models/kokoro-multi-lang-v1_0.tar.bz2 -C models
  [[ -f models/kokoro-multi-lang-v1_0/model.onnx ]] || die "Kokoro archive did not unpack correctly. Delete models/kokoro-multi-lang-v1_0* and re-run."
  ok "Kokoro voice model installed"
fi

# ------------------------------------------------------------ 6. config
bold "6/7 Configuration"
if [[ ! -f server/.env ]]; then cp server/.env.example server/.env; fi
KEY_LINE="$(grep -E '^OPENAI_API_KEY=' server/.env || true)"
KEY_VALUE="${KEY_LINE#OPENAI_API_KEY=}"
if [[ -z "$KEY_VALUE" || "$KEY_VALUE" == your-* ]]; then
  echo "  The narration step uses OpenAI. Get a key at https://platform.openai.com/api-keys"
  if [[ -t 0 ]]; then
    read -r -s -p "  Paste your OpenAI API key (input hidden): " KEY; echo
    [[ -n "$KEY" ]] || die "No key entered. Add OPENAI_API_KEY=... to server/.env and re-run."
    if grep -q '^OPENAI_API_KEY=' server/.env; then
      sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${KEY}|" server/.env
    else
      echo "OPENAI_API_KEY=${KEY}" >> server/.env
    fi
    unset KEY
  else
    die "OPENAI_API_KEY is empty. Add it to server/.env and re-run."
  fi
fi
ok "server/.env has an OpenAI key"

# The simulator shares the Mac's network, so it can use localhost.
echo "EXPO_PUBLIC_SCENE_API_URL=http://127.0.0.1:8787" > .env
ok "app points to http://127.0.0.1:8787"

# ------------------------------------------------------------- 7. checks
bold "7/7 Self-check"
server/.venv/bin/python - <<'EOF'
import importlib, sys
for m in ("fastapi", "uvicorn", "openai", "sherpa_onnx", "soundfile", "PIL", "pillow_heif", "dotenv", "multipart"):
    importlib.import_module(m)
print("  python packages import correctly")
EOF
npx --no-install tsc --version >/dev/null && ok "TypeScript available"

printf "\n\033[32mSetup complete.\033[0m\n"
if [[ $RUN_AFTER -eq 1 ]]; then
  exec "$ROOT/scripts/run.sh"
else
  echo "Start everything later with:  ./scripts/run.sh"
fi
