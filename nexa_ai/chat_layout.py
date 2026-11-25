from __future__ import annotations


CHAT_SUGGESTIONS = (
    ("Build something", "Create an app or a useful tool", "Help me build a small Python tool. Give me the complete code and setup steps."),
    ("Fix some code", "Find a bug and explain the fix", "Help me debug this code. Explain the issue and provide the corrected complete code."),
    ("Create an automation", "Design an n8n workflow", "Design an n8n workflow for this automation. Give me valid workflow JSON and explain how to import it."),
    ("Learn something", "Explain a topic step by step", "Explain a technical topic in simple Bangla with practical examples."),
)


def recent_chat_label(title: str, max_length: int = 30) -> str:
    text = " ".join(str(title or "").split())
    if not text:
        return "New conversation"
    if len(text) <= max_length:
        return text
    return text[: max(1, max_length - 1)].rstrip() + "…"
