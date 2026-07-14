"""PC Build Advisor — chatbot for PC parts & budget-based build recommendations.

Thin orchestrator only: all LLM logic lives in tools/.
Run with: streamlit run app.py
"""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from tools.pc_advisor import AdvisorError, stream_chat

st.set_page_config(page_title="PC Build Advisor", page_icon="🖥️", layout="centered")

GREETING = (
    "Hi! I'm your PC Build Advisor. Tell me your **budget** and what you'll use "
    "the PC for (gaming, editing, everyday use), and I'll recommend full "
    "part-by-part builds — an **Intel** option and an **AMD** option — with CPU, "
    "GPU, RAM, storage, and more.\n\n"
    "For example: *\"For $1000, what do you recommend for a gaming build?\"*\n\n"
    "Mention your country (or set it in the sidebar) and I'll price it in your "
    "local currency."
)

EXAMPLE_PROMPTS = [
    "For $1000, what do you recommend for a gaming build?",
    "Best $1500 build for video editing?",
    "Cheapest solid PC for everyday use and web browsing?",
    "Is DDR5 worth it over DDR4 for gaming?",
]

# Sidebar region presets -> the region string handed to the advisor (None = Auto,
# i.e. let the model infer currency from the user's messages, defaulting to USD).
REGION_PRESETS = {
    "Auto (detect from my messages)": None,
    "United States (USD, $)": "United States (USD, $)",
    "Philippines (PHP, ₱)": "Philippines (PHP, ₱)",
    "Eurozone (EUR, €)": "Eurozone (EUR, €)",
    "United Kingdom (GBP, £)": "United Kingdom (GBP, £)",
    "India (INR, ₹)": "India (INR, ₹)",
    "Canada (CAD, $)": "Canada (CAD, $)",
    "Australia (AUD, $)": "Australia (AUD, $)",
    "Other…": "OTHER",
}

with st.sidebar:
    st.header("🖥️ PC Build Advisor")
    st.caption(
        "Ask for a build by budget + use-case, or ask any PC-hardware question."
    )
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        st.error(
            "GEMINI_API_KEY not set — add it to .env and restart. "
            "Get a free key at aistudio.google.com/apikey."
        )

    st.divider()
    st.subheader("Region & currency")
    region_choice = st.selectbox(
        "Price builds for",
        list(REGION_PRESETS.keys()),
        help="Sets the default currency. You can still name a different country in chat.",
    )
    region = REGION_PRESETS[region_choice]
    if region == "OTHER":
        custom = st.text_input(
            "Your country / currency", placeholder="e.g. Japan (JPY, ¥)"
        ).strip()
        region = custom or None

    st.divider()
    st.subheader("Try an example")
    example_clicked = None
    for i, ex in enumerate(EXAMPLE_PROMPTS):
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            example_clicked = ex

    st.divider()
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("PC Build Advisor")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Greeting (not part of the model history — purely a UI welcome).
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(GREETING)

# Replay the conversation so far.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


def _handle_user_message(user_text: str, region: str = None):
    st.session_state.pending_retry = None  # a new attempt clears any prior failure
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        try:
            # The spinner shows during any brief free-tier wait/auto-retry before
            # the reply starts streaming in (st.write_stream returns the full text).
            with st.spinner("Working… (the free tier may add a brief wait)"):
                full = st.write_stream(stream_chat(st.session_state.messages, region))
            st.session_state.messages.append({"role": "assistant", "content": full})
        except AdvisorError as e:
            st.error(str(e))
            # Drop the failed user turn so history stays clean, but remember the
            # question so the user can resend it with one click (below).
            st.session_state.messages.pop()
            st.session_state.pending_retry = user_text


# Sidebar example button acts like typing that prompt.
if example_clicked:
    _handle_user_message(example_clicked, region)

# If the last question failed (e.g. a transient rate limit), offer a one-click
# resend so the user never has to retype it.
if st.session_state.get("pending_retry"):
    q = st.session_state["pending_retry"]
    st.warning("That didn't go through (the free tier was busy). Your question is saved.")
    if st.button(f"🔄 Retry: {q[:60]}{'…' if len(q) > 60 else ''}", use_container_width=True):
        _handle_user_message(q, region)

# Normal chat input.
prompt = st.chat_input("Ask about PC parts or request a build for your budget...")
if prompt:
    _handle_user_message(prompt, region)
