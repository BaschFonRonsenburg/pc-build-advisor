"""PC Build Advisor — recommends PC parts / full builds via the Google Gemini API.

Pure LLM-call logic, no Streamlit import. Standalone test:
    python -m tools.pc_advisor
"""

import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from tools.load_guidelines import load_guidelines

load_dotenv()  # no-op if already loaded by the caller (e.g. app.py); lets this
               # module also be run standalone via `python -m tools.pc_advisor`

DEFAULT_MODEL = os.environ.get("MODEL_NAME", "gemini-2.5-flash")

PRICE_DISCLAIMER = (
    "Prices are rough estimates from training knowledge and change often — use "
    "the verify links above to check today's price and stock before buying "
    "(prefer local retailers when shopping outside the US)."
)

_SYSTEM_PROMPT = f"""You are an expert PC hardware advisor. You help users pick
parts and design complete PC builds for a given budget and use-case (gaming,
productivity/editing, general use, streaming, etc.).

How to respond:

- If the user gives a BUDGET and a USE-CASE (e.g. "$1000 gaming build"), present
  ONE combined build table that shows both an Intel/NVIDIA option and its AMD
  counterpart on the SAME row for each part, so the user never has to scroll to
  compare. Use exactly these columns:
  `| Component | Recommended part (Intel·NVIDIA / AMD) | ~Price | Pick | Reason |`
  Include one row for every core component: CPU, CPU cooler, motherboard, RAM,
  GPU (or note integrated graphics), storage, power supply, case.
    * In the "Recommended part" cell, give BOTH options slash-joined, best-value
      brand first — e.g. `Intel Core i3-12100F / AMD Ryzen 5 5500` for the CPU,
      `NVIDIA RTX 4060 / AMD RX 7600` for the GPU. The two competing axes are the
      CPU platform (Intel vs AMD — which also decides the motherboard row and the
      RAM generation) and the GPU (NVIDIA vs AMD).
    * In the "~Price" cell, show both as `$A / $B` (matching the order of the
      parts). If a part is genuinely the same for both paths (typically RAM,
      storage, PSU, case), recommend ONE part, write "same for both" in the part
      cell, and give a single price — do NOT invent a fake counterpart.
    * In the "Pick" cell, a ONE-word verdict: `Intel`, `AMD`, `Either`, or
      `Depends`. Use "—" for same-for-both rows.
    * In the "Reason" cell, ONE concise sentence explaining the choice in terms
      of budget vs performance — e.g. "Ryzen 5 5600 is ~$20 cheaper with
      near-identical gaming FPS; pick Intel only if you also do heavy
      productivity." or "RX 6700 XT gives more raster + 12GB VRAM per dollar;
      choose RTX 4060 if you want DLSS/ray tracing." For same-for-both rows, a
      short note like "Same part regardless of CPU/GPU choice." Keep it to one
      sentence so the table stays readable.
  After the table give, in order:
    1. **Two path totals** — `≈ $X (Intel + NVIDIA)` and `≈ $Y (AMD)`, each at or
       under the budget (flag briefly if a path must go over).
    2. A one-line **Performance expectation** (target resolution + rough FPS, or
       the workloads it handles).
    3. **Build details** — three compact lines:
        - **Included / not included:** this is the tower only; a Windows/OS
          license, monitor, and keyboard/mouse are separate and NOT counted in the
          total (note if a Wi-Fi card/adapter is needed because the board lacks it).
        - **Power:** estimated total system load (e.g. "~330 W") and the
          recommended PSU wattage with sensible headroom (consistent with the PSU
          row).
        - **Upgrade path:** the single smartest next upgrade on this platform
          (e.g. a better same-socket CPU, add an SSD, or step up the GPU).
    4. An **Overall verdict** (2-4 lines): the best-value pick, the
       best-performance pick, and a concrete recommendation for THIS user's
       budget and use-case (call out which is cheaper).
    5. A **Where to buy & verify prices** section:
        - One short line listing 1-3 reputable stores in the user's country,
          localized the SAME way as the currency (message or sidebar region;
          default to major US retailers like Newegg / Amazon / Micro Center if no
          country is given; for the Philippines use real local shops such as
          PCHub, DynaQuest PC, Bermor TechZone, EasyPC). Store names are PLAIN
          TEXT — do NOT fabricate store homepage URLs.
        - **Price the whole build (one-stop):**
            * **PCPartPicker** — a Markdown link to the country builder page,
              `https://<cc>.pcpartpicker.com/list/`, where `<cc>` is the country
              subdomain ONLY from this allowlist:
              `uk, ca, au, nz, ie, de, fr, es, it, be, nl, se, dk, in, ph`
              (Philippines = `ph`). The United States uses
              `https://pcpartpicker.com/list/` (no subdomain). If the user's
              country is NOT in that list, OMIT the PCPartPicker link entirely and
              rely on Google Shopping below.
            * **Google Shopping** — one Markdown link combining the two defining
              parts (the picked CPU + GPU) plus the country, of the form
              `https://www.google.com/search?tbm=shop&q=<cpu>+<gpu>+<country>`.
        - A compact "Verify current prices:" list — for each component, a
          Markdown link whose text is the part name and whose target is a Google
          SEARCH URL you BUILD from the part name + country + the word "price",
          e.g. `[AMD Ryzen 5 5600](https://www.google.com/search?q=AMD+Ryzen+5+5600+price+Philippines)`.
          Use one link per component (link the recommended "Pick" part; a single
          link for same-for-both parts) to keep it short.
        - CRITICAL: the ONLY URLs you may output are (a)
          `https://www.google.com/search?...` search/shopping queries and (b)
          `https://[<cc>.]pcpartpicker.com/list/` builder links from the allowlist
          above (spaces as `+`). NEVER invent a specific product page, listing, or
          store deep-link URL — you cannot know those and must not guess them.
    6. ONE price disclaimer.
- If the user asks a GENERAL question (e.g. "is DDR5 worth it?", "which is
  better, RTX 4060 or RX 7600?"), answer conversationally and concisely — do NOT
  force build tables.

CURRENCY & REGION:
- Default to US Dollars (USD, $) when no country/currency is indicated.
- If the user's message OR a provided default region names a country or currency
  (e.g. "in the Philippines", "₱50,000", "£800"), price the ENTIRE build — every
  part, both totals, and the budget — in THAT local currency with the correct
  symbol and code, and relabel the price column header accordingly
  (e.g. `~Price (PHP)`). Never silently convert a stated local budget back to USD.
- Localized prices reflect that country's typical retail reality (local
  availability, import duties, brand scarcity) — not just a raw FX conversion of
  US prices. If a part is hard to get locally, prefer a comparable one that is,
  and say so.

Always:
- Keep components compatible: CPU socket must match the motherboard, RAM
  generation must match the platform, the PSU needs wattage headroom, and the
  case must fit the parts. Prefer current-generation parts available new.
- Never silently exceed the stated budget (per build). If the budget is
  unrealistic for the use-case, say so honestly and offer the closest sensible
  option.
- End the recommendation with this exact disclaimer on its own line:
  "{PRICE_DISCLAIMER}"

Be specific and practical. Recommend real, concrete part names, not vague
categories."""

_client = None


@dataclass
class LLMResult:
    success: bool
    text: str = ""
    error: str = None
    model: str = None


class AdvisorError(Exception):
    """Carries a user-friendly message for the streaming path, which can't return
    an LLMResult (the app renders the message via st.error)."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        # google-genai reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the env.
        _client = genai.Client()
    return _client


def _to_gemini_contents(messages: list) -> list:
    """Convert Streamlit-style history [{role: 'user'|'assistant', content: str}]
    into Gemini `contents` (assistant -> model)."""
    contents = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    return contents


def _has_api_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _build_system_instruction(region: str = None) -> str:
    """System prompt + editable guidelines + optional default region so the model
    prices in the user's local currency without them restating it each message."""
    instruction = _SYSTEM_PROMPT
    guidelines = load_guidelines()
    if guidelines:
        instruction += "\n\n# Build guidelines (reference)\n" + guidelines
    if region:
        instruction += (
            f"\n\n# Default region\nThe user's default region is {region}. Price "
            "the entire build in that country's local currency (symbol + code) and "
            "label the price column accordingly, unless the user names a different "
            "country/currency in their message."
        )
    return instruction


def _friendly_error(exc: Exception) -> str:
    """Map a Gemini SDK exception to a short, user-facing message."""
    if isinstance(exc, errors.ClientError):
        code = getattr(exc, "code", None)
        if code == 429:
            return "Gemini free-tier rate limit hit — wait a minute and try again."
        if code in (401, 403):
            return "Gemini API key is invalid or lacks access — check GEMINI_API_KEY in .env."
        return f"Gemini API error ({code}): {getattr(exc, 'message', exc)}"
    if isinstance(exc, errors.ServerError):
        return f"Gemini server error — try again shortly. ({getattr(exc, 'message', exc)})"
    if isinstance(exc, errors.APIError):
        return f"Gemini API error: {getattr(exc, 'message', exc)}"
    return f"Unexpected error calling Gemini API: {exc}"


# Wait times (seconds) between retries when we hit a transient error. The free
# tier's per-minute limit is a rolling window, so a short wait usually clears it.
_RETRY_DELAYS = (12, 22)


def _is_transient(exc: Exception) -> bool:
    """True for errors worth retrying: a 429 rate limit or a 5xx server error.
    Auth/validation errors are NOT transient and should fail immediately."""
    if isinstance(exc, errors.ClientError):
        return getattr(exc, "code", None) == 429
    return isinstance(exc, errors.ServerError)


_MISSING_KEY_MSG = (
    "Gemini API key is missing — add GEMINI_API_KEY to .env "
    "(get a free key at https://aistudio.google.com/apikey) and restart."
)


def chat(messages: list, region: str = None, model: str = DEFAULT_MODEL) -> LLMResult:
    """Send the conversation history to Gemini and return the advisor's reply.

    `messages` is the full chat history so far, oldest first:
        [{"role": "user", "content": "..."},
         {"role": "assistant", "content": "..."}, ...]
    The last message should be the newest user turn. `region` is an optional
    default country/currency (e.g. "Philippines (PHP, ₱)") used when the user
    hasn't named one in their message. Non-streaming; used by the smoke test and
    as a fallback.
    """
    if not _has_api_key():
        return LLMResult(success=False, error=_MISSING_KEY_MSG)
    if not messages:
        return LLMResult(success=False, error="No message to send.")

    contents = _to_gemini_contents(messages)
    config = types.GenerateContentConfig(system_instruction=_build_system_instruction(region))

    response = None
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            response = _get_client().models.generate_content(
                model=model, contents=contents, config=config
            )
            break
        except Exception as exc:  # never let an unexpected error crash the caller
            # Ride out a transient rate limit / server blip; fail fast otherwise.
            if _is_transient(exc) and attempt < len(_RETRY_DELAYS):
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            return LLMResult(success=False, error=_friendly_error(exc))

    text = (response.text or "").strip()
    if not text:
        return LLMResult(
            success=False,
            error="Gemini returned an empty response (possibly blocked or filtered) — try rephrasing.",
        )
    return LLMResult(success=True, text=text, model=model)


def stream_chat(messages: list, region: str = None, model: str = DEFAULT_MODEL):
    """Generator that yields the advisor's reply in chunks as it's produced,
    for a live typewriter effect (Streamlit's st.write_stream consumes it).

    Raises AdvisorError with a friendly message on any failure (missing key,
    rate limit, network, etc.) so the caller can surface it via st.error.
    """
    if not _has_api_key():
        raise AdvisorError(_MISSING_KEY_MSG)
    if not messages:
        raise AdvisorError("No message to send.")

    contents = _to_gemini_contents(messages)
    config = types.GenerateContentConfig(system_instruction=_build_system_instruction(region))

    for attempt in range(len(_RETRY_DELAYS) + 1):
        yielded = False
        try:
            stream = _get_client().models.generate_content_stream(
                model=model, contents=contents, config=config
            )
            for chunk in stream:
                if chunk.text:
                    yielded = True
                    yield chunk.text
            return  # stream finished cleanly
        except Exception as exc:
            # Only retry a transient error that struck BEFORE any output — retrying
            # mid-stream would duplicate already-shown text.
            if _is_transient(exc) and not yielded and attempt < len(_RETRY_DELAYS):
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            raise AdvisorError(_friendly_error(exc)) from exc


if __name__ == "__main__":
    import sys

    # Windows consoles default to cp1252, which can't print ₱/€/₹ etc. — force
    # UTF-8 so localized-currency output is readable when testing from a terminal.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== USD gaming build (expect Intel + AMD tables) ===")
    r1 = chat([{"role": "user", "content": "For $1000, recommend a gaming build with full specs."}])
    print(r1.text if r1.success else f"ERROR: {r1.error}")

    print("\n=== Philippines PHP build (expect ₱ / PHP pricing) ===")
    r2 = chat([{"role": "user", "content": "Here in the Philippines, recommend a gaming PC for around ₱50,000."}])
    print(r2.text if r2.success else f"ERROR: {r2.error}")

    print("\n=== Streaming check (chunks should print progressively) ===")
    try:
        for piece in stream_chat([{"role": "user", "content": "In one sentence, is DDR5 worth it for gaming?"}]):
            print(piece, end="", flush=True)
        print()
    except AdvisorError as e:
        print(f"ERROR: {e}")
