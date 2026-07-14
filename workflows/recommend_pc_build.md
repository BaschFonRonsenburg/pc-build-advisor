# Workflow: Recommend PC Parts / Full Build (Chatbot)

## Objective
Let a user chat about PC hardware and, given a budget + use-case (e.g. "For
$1000, what's a good gaming build?"), return a complete, part-by-part build
recommendation (CPU, cooler, motherboard, RAM, GPU, storage, PSU, case) with
approximate prices, an estimated total, a performance expectation, and reasoning
— all for free using the model's own hardware knowledge.

## When This Runs
Triggered interactively whenever the user sends a message in the Streamlit chat
(`app.py`). Not automated/scheduled.

## Required Inputs
- A user message (budget + use-case for a full build, or any PC-hardware
  question).
- A valid `GEMINI_API_KEY` in `.env` (free key from
  https://aistudio.google.com/apikey).

## Tools Used (in order)
1. `tools/load_guidelines.py :: load_guidelines()`
   → returns the editable steering text from `data/build_guidelines.md`
   (called inside the system-instruction builder; injected into the prompt).
2. `tools/pc_advisor.py :: stream_chat(messages, region)`
   → streams the advisor's reply chunk-by-chunk to the app (`st.write_stream`),
   raising `AdvisorError` on failure. `region` is the sidebar's default
   country/currency (or None = Auto). `chat(messages, region)` is the
   non-streaming equivalent returning an `LLMResult` (used by the smoke test).

## Expected Outputs
- **Full build request** → **one combined table** with columns
  `Component | Recommended part (Intel·NVIDIA / AMD) | ~Price | Pick | Reason`,
  showing both an Intel/NVIDIA option and its AMD counterpart per row (brand-
  agnostic parts marked "same for both"), a one-word **Pick** and a one-sentence
  **Reason** (budget vs performance) per row, followed by **two path totals**
  (Intel+NVIDIA vs AMD), a **Performance expectation**, **Build details**
  (included vs not / est. wattage + PSU headroom / upgrade path), an **Overall
  verdict**, a **Where to buy & verify prices** block (localized store names, a
  one-stop "price the whole build" link — PCPartPicker localized + Google
  Shopping — and one Google search "verify price" link per part), and one price
  disclaimer.
- **Currency** → USD by default; if the user names a country/currency, or a
  default region is set in the sidebar, the entire build (parts, totals, budget)
  is priced in that local currency with the column header relabeled (e.g.
  `~Price (PHP)`).
- **General question** → a concise conversational answer (no forced tables).
- All recommendations are estimates for human verification — nothing is
  purchased or ordered.

## Edge Cases & Failure Handling
- **Missing API key** → friendly in-app error (sidebar + on send); app does not
  crash. `chat()` returns a clear `LLMResult.error`.
- **Rate limit / quota (429)** → free-tier-friendly "wait a minute" message.
- **Invalid key / no access (401/403)** → message pointing at `.env`.
- **Server error (5xx) / network** → "try again shortly" message.
- **Empty/blocked response** → asks the user to rephrase.
- **Unrealistic budget** → the model says so honestly and offers the closest
  sensible option (handled via the system prompt + guidelines).
- **Vague request** (no budget or use-case) → the model asks a clarifying
  question rather than guessing.
- On any failure the failed user turn is removed from history so retries don't
  stack a broken conversation.

## Notes on Pricing
- Prices come from the model's training knowledge, not a live feed, so every
  price/build answer ends with a disclaimer to verify current prices before
  buying. This keeps the project free and zero-maintenance. If live pricing is
  ever needed, add a pricing tool and feed results into the prompt — no change
  to the chat orchestration is required.

## Tuning Without Code Changes
Edit `data/build_guidelines.md` to change budget-allocation rules, compatibility
reminders, or output expectations. The file is injected into the system
instruction at runtime.

## Lessons Learned
_(Update this section as real usage surfaces quirks — quota limits, prompt
tweaks that improved build quality, component recommendations that were off,
etc., per the self-improvement loop in `CLAUDE.md`.)_
