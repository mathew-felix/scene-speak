"""Narration step: turns the vision model's factual inventory into a spoken-style description.

The language model is only a writer here. It is told that the inventory is the only truth, so it
should rephrase and order the facts, not invent new ones (see SYSTEM_PROMPT).
"""

from __future__ import annotations

import logging

import openai
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("scenespeak.openai")

# gpt-3.5-turbo has been retired for many accounts; fall back automatically.
FALLBACK_MODELS = ("gpt-4o-mini", "gpt-4.1-mini")

# The system prompt fixes the model's role, the order of the narration and the strict rules
# (no guessing, no filler, keep colors/counts/positions). Low temperature below keeps it faithful.
SYSTEM_PROMPT = (
    "You write audio descriptions for blind and low-vision listeners. "
    "You receive a verified inventory of one image. It is the only truth.\n\n"
    "Write one flowing description in this order:\n"
    "1) One sentence stating what the image is and its overall setting.\n"
    "2) The main subject, with colors and position.\n"
    "3) Other objects, then people, then animals or insects (clothing, action, direction), "
    "then any text, then the background.\n\n"
    "Rules:\n"
    "- Use every fact from the inventory. Keep colors, counts and positions exactly as given.\n"
    "- Add nothing: no objects, people, weather, time of day, sounds, smells, feelings, symbolism "
    "or opinions. No guesses (\"probably\", \"seems\", \"might\").\n"
    "- No filler or commentary (\"beautiful\", \"adding to the scene\", \"creating a vibrant "
    "atmosphere\").\n"
    "- Describe positions from the viewer's perspective, in plain words (\"on the left\", "
    "\"in the background\").\n"
    "- Skip any section marked \"none visible\". Do not mention it.\n"
    "- Read any listed text word for word, in quotes.\n"
    "- Plain spoken prose, 90 to 170 words, 1 to 3 short paragraphs. No lists, headings or "
    "markdown. Use numerals sparingly, since it is spoken."
)


class StoryError(RuntimeError):
    """User-facing failure while generating the narration."""


def _candidate_models() -> list[str]:
    """Models to try in order: the configured one first, then fallbacks (without duplicates)."""
    models = [OPENAI_MODEL]
    models.extend(m for m in FALLBACK_MODELS if m != OPENAI_MODEL)
    return models


def elaborate_story(scene_context: str) -> str:
    """Send the inventory to OpenAI and return the narration text. Raises StoryError on failure."""
    if not OPENAI_API_KEY:
        raise StoryError("OPENAI_API_KEY is not set in server/.env")

    # timeout: give up on a hung request after 60 s; max_retries: the SDK itself retries
    # transient network/5xx errors twice before raising.
    client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0, max_retries=2)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Verified image inventory:\n{scene_context}\n\n"
            "Write the narrative now, using only what is stated above.",
        },
    ]

    last_error: Exception | None = None
    for model in _candidate_models():
        try:
            # temperature 0.2 = very little randomness (stay close to the facts);
            # max_tokens 450 comfortably fits the 90-170 word target.
            response = client.chat.completions.create(
                model=model, temperature=0.2, max_tokens=450, messages=messages
            )
            story = (response.choices[0].message.content or "").strip()
            if not story:
                raise StoryError("OpenAI returned an empty narration")
            if model != OPENAI_MODEL:
                logger.warning("Used fallback model %s (configured: %s)", model, OPENAI_MODEL)
            return story
        # Error handling: "model not found" means try the next model; every other failure
        # is final and gets a message the app can show to the user.
        except openai.NotFoundError as exc:
            last_error = exc
            logger.warning("Model %s unavailable: %s", model, exc)
            continue
        except openai.AuthenticationError as exc:
            raise StoryError("OpenAI rejected the API key. Check OPENAI_API_KEY in server/.env") from exc
        except openai.RateLimitError as exc:
            raise StoryError("OpenAI quota or rate limit reached. Check billing on your account") from exc
        except openai.APIConnectionError as exc:
            raise StoryError("Could not reach OpenAI. Check the internet connection on the Mac") from exc

    raise StoryError(f"No OpenAI model was available ({last_error})")
