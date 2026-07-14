# PC Build Advisor

A chatbot that recommends PC parts and full builds. Tell it your **budget** and
**use-case** (e.g. *"For $1000, what do you recommend for a gaming build?"*) and
it returns **one side-by-side build table** where each part shows an
**Intel/NVIDIA** option and its **AMD** counterpart together (e.g. `Intel Core
i3-12100F / AMD Ryzen 5 5500`) — covering CPU, cooler, motherboard, RAM, GPU,
storage, PSU, and case — with approximate prices, a one-word **Pick** and a
one-sentence **Reason** (budget vs performance) per part, two path totals
(Intel+NVIDIA vs AMD), expected performance, and an overall verdict. Mention your
country (or set it in the sidebar)
and prices are shown in your **local currency** (e.g. ₱ PHP), along with
localized **store suggestions and one-click "verify price" search links** per
part. Responses stream in live, and you can also ask general PC-hardware
questions.

Free to run: it uses the **Google Gemini free tier** and the model's own
hardware knowledge (no paid APIs, no scraping).

> Prices are estimates from the model's training data, not a live feed — always
> verify current prices before buying.

## Preview

![PC Build Advisor preview](docs/preview.svg)

<sub>Illustrative mockup of the chat UI. To use a real screenshot instead: run
`streamlit run app.py`, capture the chat, save it as `docs/screenshot.png`, and
point the image above at that file.</sub>

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Get a **free** Gemini API key at https://aistudio.google.com/apikey.
3. Copy `.env.example` to `.env` and paste your key:
   ```
   cp .env.example .env
   ```
   ```
   GEMINI_API_KEY=your-key-here
   MODEL_NAME=gemini-2.5-flash
   ```
4. Run the app:
   ```
   streamlit run app.py
   ```

## Project layout

- `app.py` — Streamlit chat UI (thin orchestrator, calls into `tools/` only);
  includes the sidebar region/currency selector and live streaming
- `tools/pc_advisor.py` — the Gemini calls: `stream_chat(messages, region)`
  (streaming generator used by the app) and `chat(messages, region)` (returns an
  `LLMResult`, used by the smoke test)
- `tools/load_guidelines.py` — loads the editable steering text
- `data/build_guidelines.md` — **editable** build heuristics (budget allocation,
  compatibility rules, output format) injected into the prompt — no code changes
  needed to tune the advice
- `workflows/recommend_pc_build.md` — SOP for the recommendation flow

## Tuning the advice

Edit `data/build_guidelines.md` to change how builds are balanced or formatted.
The file is injected into the model's system instruction at runtime, so changes
take effect on the next message.

## Testing individual tools

```
python -m tools.load_guidelines     # prints the guidelines
python -m tools.pc_advisor          # runs a sample "$1000 gaming build" query
```

## License

Released under the [MIT License](LICENSE).
