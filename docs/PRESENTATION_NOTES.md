# SceneSpeak: Presentation Notes

## One-line pitch
Take a photo and hear it described: a faithful, calm audio description for blind and low-vision people, played like a music library.

## Suggested slide outline (10 slides)

1. **Title**: SceneSpeak, with logo and tagline.
2. **Problem**: Images are inaccessible to blind and low-vision users. Alt text is often missing or generic. Existing tools can invent details.
3. **Solution**: Add a photo with +, get a spoken description, and replay it from a gallery.
4. **Demo flow**: login → + button → processing stages → gallery card → play audio.
5. **Architecture**: Use the diagram in `ARCHITECTURE.md` (app → Mac backend → Qwen → GPT → Kokoro → audio).
6. **Pipeline detail**: The vision model observes and the language model narrates, with no invented facts.
7. **Design for accessibility**: Calm, low-motion UI, dark theme, large targets, audio-first.
8. **Engineering challenges**: See the table below.
9. **Results**: About 30 s per photo, with the image processed locally.
10. **Future work and Q&A**.

## Key talking points
- **Faithfulness first.** The inventory is the only source of truth. The narration prompt forbids guesses, filler and feelings.
- **Hybrid design.** Vision and speech run locally on a laptop. Only text goes to the cloud LLM.
- **Privacy.** The photo never leaves the Mac.
- **Graceful failure.** A failed job is never saved to the gallery, and the user sees a clear message.
- **One-command setup.** `./scripts/setup.sh` installs the tools, downloads the models and launches the app in the Simulator, so anyone can clone and run it.

## Tech stack
| Layer | Technology |
|---|---|
| App | Expo SDK 58, React Native 0.88, TypeScript, Expo Router, Reanimated 4, expo-audio |
| Backend | Python 3.12, FastAPI, uvicorn |
| Vision | Qwen3.5-2B Q4_K_M + mmproj via llama.cpp `llama-server` |
| Narration | OpenAI gpt-4o-mini (fallback gpt-4.1-mini) |
| Speech | Kokoro multi-lang v1.0 via sherpa-onnx |
| Build | Xcode and the iOS Simulator (`scripts/setup.sh`, `scripts/run.sh`) |

## Challenges and how we solved them
| Challenge | Solution |
|---|---|
| Small vision model repeated itself and invented sizes | Labelled-line prompt, repeat penalty, no brackets, relative sizes, output cleaning |
| 9B model too slow on a 16 GB laptop | Settled on the 2B model, with an acceptable quality/speed trade-off |
| "Can't reach server" in the Simulator | `localhost` resolved to IPv6 while the server uses IPv4. Fixed by using `127.0.0.1` |
| "Unsupported FormDataPart" on upload | Upload with `expo/fetch` and an `expo-file-system` `File` |
| `expo-av` did not compile on SDK 58 | Switched to `expo-audio` |
| `llama-server` left running after shutdown | API lifespan hook that stops it |
| GPT-3.5 retired | Use gpt-4o-mini with an automatic fallback |
| Narration added filler | Strict system prompt with a fixed order and a word limit |
| Lost work in a rollback | Rebuilt the app, and now commit to git early |

## Example output
Input: a waterfall photo.
Inventory: "Setting: a rocky cliffside with water flowing over it under bright sunlight. Main subject: a waterfall cascading into the sea..."
Narration: "The image depicts a rocky cliffside with water flowing over it under bright sunlight. The main subject is a waterfall cascading down into the sea below... In the left foreground, there are mossy rocks, with green plants growing among them..."
Audio: about 1.2 MB WAV, 24 kHz.

## Demo checklist
- Server running (`./scripts/run.sh`) and `http://127.0.0.1:8787/health` returns ok.
- Simulator open on the iPhone 18 Pro, signed in with `admin@gmail.com` / `admin`.
- A few test photos already dragged into the Simulator (landscape, people, animals, text).
- Have a backup: a pre-recorded video, and a pre-generated audio file.

## Likely questions
- **Why not describe with GPT-4 vision?** Local vision protects privacy and cost. Splitting roles also reduces hallucination.
- **How accurate is it?** It is limited by the 2B model. It states only what it saw and omits uncertain items.
- **Does it work offline?** The vision and speech steps do. The narration step needs internet.
- **Can it scale?** Move the backend to a server with a GPU and add authentication.
