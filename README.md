# SceneSpeak

SceneSpeak turns a photo into a spoken description, built for blind and low-vision users. Tap **+**, pick a photo, and about 30 seconds later you can listen to a description of it. Your scenes are saved in a gallery you can replay like music.

```
Photo → Qwen3.5-2B vision (runs on your Mac) → GPT narration (OpenAI) → Kokoro voice (runs on your Mac) → audio
```

This guide assumes you have never set up a project like this before. Follow the steps in order. Nothing is skipped.

---

## What you need before you start

| You need | Why | How to check or get it |
|---|---|---|
| A **Mac** with 8 GB RAM or more and **12 GB free disk space** | The AI models run on your Mac. Windows and Linux are **not** supported | Apple menu > About This Mac |
| **Xcode** (free, about 10 GB) | It provides the iPhone Simulator that runs the app | Install from the Mac App Store |
| **Homebrew** | It installs the other tools for you | See step 2 |
| An **OpenAI API key** | It writes the narration. It costs a fraction of a cent per photo | See step 3 |
| An internet connection | The first setup downloads about 2.2 GB of models | |

---

## Step by step

### 1. Install Xcode and open it once
1. Open the **App Store**, search for **Xcode**, and install it. This takes a while.
2. Open Xcode once. Click **Agree** and let it install extra components if it asks.
3. In Xcode, open **Settings > Components** (it may say **Platforms**). If no iOS Simulator is listed, click **Get** next to the latest **iOS** and wait for the download.
4. Close Xcode.

### 2. Install Homebrew
1. Open **Terminal**. Press `Cmd + Space`, type `Terminal`, press Enter.
2. Go to https://brew.sh, copy the install command, paste it into Terminal, and press Enter.
3. When it finishes, it prints **Next steps**. Run the commands it shows. They usually start with `echo` and `eval`.
4. Check it worked by typing `brew --version`. You should see a version number.

### 3. Get an OpenAI API key
1. Create an account at https://platform.openai.com and add a small amount of credit (5 USD is plenty).
2. Open https://platform.openai.com/api-keys and click **Create new secret key**.
3. Copy the key (it starts with `sk-`). **Keep it private. Never share it or put it on GitHub.**

### 4. Download the project
In Terminal, run:

```bash
git clone https://github.com/mathew-felix/scene-speak.git
cd scene-speak
```

If your Mac asks to install the **command line developer tools**, click **Install**, wait, then run the two commands again.

### 5. Run the setup script
```bash
./scripts/setup.sh
```

What it does, all by itself:
1. Checks your Mac, Xcode and the iPhone Simulator.
2. Installs Node, CocoaPods, llama.cpp, Watchman and Python 3.12 (through Homebrew) if you don't have them.
3. Installs the app and server libraries.
4. Downloads the AI models (about 2.2 GB) into `models/`.
5. **Asks you to paste your OpenAI key.** Paste it and press Enter. Nothing shows on screen while you type. That is normal.
6. Starts the server, then builds the app and opens it in the iPhone Simulator.

**Be patient.** The first run takes about **15 to 30 minutes**, mostly downloading and the first app build. It may ask for your Mac password once, to accept the Xcode license. Don't close Terminal.

When it is done, a Simulator window opens with SceneSpeak running.

### 6. Try the app
1. On the login screen, sign in with email `admin@gmail.com` and password `admin`. (A temporary built-in login for testing.)
2. Get a photo into the Simulator: drag any photo from your Mac **onto the Simulator window**. It lands in the Photos app.
3. In SceneSpeak, tap the **+** button, then **Choose from library**, and pick the photo.
4. Allow photo access if asked.
5. Wait about 30 seconds. You will see progress: looking at the photo, writing the description, creating the audio.
6. The scene appears in the gallery. Tap it to hear it. Make sure your Mac volume is on.

If anything fails, the photo is **not** added, and the app tells you why.

---

## Running it again later

You only run the setup once. Next time, from the project folder:

```bash
./scripts/run.sh
```

To stop everything, click in Terminal and press `Ctrl + C`.

---

## If something goes wrong

The setup script stops with a clear message when something is missing. Fix that one thing, then run `./scripts/setup.sh` again. It is safe to repeat and skips what is already done. Downloads resume where they stopped.

| What you see | What to do |
|---|---|
| `Xcode is not installed` | Do step 1, then run the script again |
| `No iOS Simulator runtime found` | Xcode > Settings > Components, download an iOS runtime |
| `Homebrew is not installed` | Do step 2 |
| `command not found: git` | Run `xcode-select --install`, wait, try again |
| `permission denied` when running a script | Run `chmod +x scripts/*.sh`, then try again |
| A download fails or freezes | Check your internet, then run `./scripts/setup.sh` again |
| `OPENAI_API_KEY is not set` | Open `server/.env`, write `OPENAI_API_KEY=sk-your-key` on that line, save, run `./scripts/run.sh` |
| OpenAI says the key is invalid or over quota | Check the key and your credit at https://platform.openai.com |
| The app says `Can't reach the SceneSpeak server` | The server isn't running. Run `./scripts/run.sh`. Test it with `curl http://localhost:8787/health`, which should print `{"status":"ok"...}` |
| `Port 8787 already in use` | Run `pkill -f "uvicorn app:app"`, then `./scripts/run.sh` |
| The login does not accept my details | Use `admin@gmail.com` and `admin`, exactly |
| The first build is very slow | This is normal. Later builds are much faster |
| Your Mac gets slow or hot | Close other big apps. The vision model needs about 3 GB of RAM |

Still stuck? Look at the logs: `server/outputs/server.log` and `server/outputs/llama-server.log`. Include them when you ask for help.

---

## Settings

`server/.env` holds your settings. It is created by the setup script, and git ignores it, so your key is never uploaded.

| Setting | Meaning | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI key | none |
| `OPENAI_MODEL` | Narration model | `gpt-4o-mini` |
| `SCENE_SPEAK_PORT` | Server port | `8787` |

---

## Privacy

Your photo is described on your own Mac and is **never sent to OpenAI**. Only the text description goes to OpenAI, to write the narration.

---

## How it works (short version)

| Part | Technology |
|---|---|
| App | Expo SDK 58, React Native, TypeScript, Expo Router |
| Server | Python 3.12, FastAPI |
| Vision | Qwen3.5-2B through llama.cpp |
| Narration | OpenAI gpt-4o-mini |
| Voice | Kokoro through sherpa-onnx |

More detail is in `docs/ARCHITECTURE.md`.

```
src/        the app
server/     the backend
models/     AI models (downloaded by setup, not stored in git)
scripts/    setup.sh and run.sh
docs/       design and presentation notes
```

For developers: `npm run server`, `npx expo start`, `npm run lint`, `npm run typecheck`.
