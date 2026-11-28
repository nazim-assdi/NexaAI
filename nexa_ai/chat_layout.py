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

RESPONSE_PROFILES = {"Quick": 1024, "Balanced": 2048, "Detailed": 3072}

def response_token_limit(profile: str) -> int:
    return RESPONSE_PROFILES.get(str(profile), RESPONSE_PROFILES["Detailed"])

def build_chat_context(messages: list[dict], max_recent_messages: int = 8) -> list[dict]:
    """Keep the system prompt and a bounded recent window for faster CPU prompt processing."""
    system = [item for item in messages if item.get("role") == "system"][:1]
    history = [item for item in messages if item.get("role") != "system"]
    return system + history[-max(2, int(max_recent_messages)):]

def enqueue_followup(queue: list[str], text: str, limit: int = 4) -> bool:
    value = str(text).strip()
    if not value or len(queue) >= max(0, int(limit)):
        return False
    queue.append(value)
    return True

def take_followup(queue: list[str]) -> str | None:
    return queue.pop(0) if queue else None
