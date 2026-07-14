"""Loads the editable build guidelines that steer the advisor.

Pure file-read logic, no Streamlit import. Standalone test:
    python -m tools.load_guidelines
"""

import os

_GUIDELINES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "build_guidelines.md",
)


def load_guidelines(path: str = _GUIDELINES_PATH) -> str:
    """Return the build-guidelines text, or "" if the file is missing/unreadable
    so the app can degrade gracefully (the advisor still works, just without the
    extra steering)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        return ""


if __name__ == "__main__":
    text = load_guidelines()
    if text:
        print(text)
    else:
        print("(no guidelines file found)")
